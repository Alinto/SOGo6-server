# SOGo 6 â€” MFA backend technical spec

Nov 16, 2026 Â· @Quentin H

## Context & goal

The SOGo 6 backend (Python / Flask REST API) gets multi-factor authentication at login, with two methods at launch: **TOTP** and **External OTP**. External OTP connects SOGo to an outside service over HTTP, either to deliver a code SOGo generates (SMS gateway) or to validate the code the user types (an MFA server such as privacyIDEA or LinOTP). The design must make a third method (WebAuthn, email code, pushâ€¦) a matter of adding one provider class, not reworking the login flow.

MFA applies to **webmail login only**. Per domain, the admin sets which methods are allowed (the existing SOGo 6 allowed-methods parameter) and whether MFA is enforced. A user has at most one active method at a time:

| Allowed methods | Enforced | What the user does |
| --- | --- | --- |
| One | No | May set up that method in preferences, or not |
| One | Yes | Must set it up (forced enrollment at next login if not done) |
| Several | No | May set up one of them in preferences, choosing which |
| Several | Yes | Must choose one and set it up, in preferences or at forced enrollment |

So an admin who wants everyone on External OTP allows only `external_otp` and enforces MFA; an admin who wants to leave the choice allows both.

A user who loses their device is handled by an admin reset; there are no recovery codes. This spec covers the backend only; the React / Next.js frontend consumes the endpoints described in Technical design.

## Use cases

Seven use cases cover the launch scope. Each acceptance criterion should map to at least one automated test.

| # | Actor | Use case | Acceptance criteria |
| --- | --- | --- | --- |
| UC1 | User | Choose and set up a method in preferences | Only allowed methods are offered. TOTP: backend returns a secret and an `otpauth://` URI, and the method is saved after one valid code. External OTP: saved after one successful challenge (code received and typed back). |
| UC2 | User | Switch or disable their method | Switching = setting up the new method; it replaces the old one once confirmed. Disabling requires a valid current code and is refused with 403 when MFA is enforced. |
| UC3 | User | Log in with TOTP | After a valid password, no session is issued until a valid code is submitted. Codes from the previous, current and next 30 s step are accepted; a code is accepted once only. |
| UC4a | User | Log in with External OTP, send mode | After a valid password, SOGo generates a 6-digit code, sends it through the configured request (e.g. SMS gateway) and checks it itself. The code is valid 5 min. |
| UC4b | User | Log in with External OTP, validate mode | After a valid password, SOGo optionally calls a trigger request (e.g. to make the MFA server send an SMS). The code the user types is sent to the external service, whose answer decides. |
| UC5 | Admin | Configure MFA | Admin sets allowed methods, enforcement and, if allowed, the External OTP mode, requests with placeholders (`US_MAPPING` keys plus `{code}`) and success rule, globally or per domain. Invalid values are refused on save with a clear error. |
| UC6 | Admin | Force MFA | Every login requires a second factor. A user with no method gets an MFA session limited to enrollment; if several methods are allowed, they choose one, then set it up before getting a session. |
| UC7 | Admin | Reset a user's MFA | Clears the user's `mfa_method` (lost phone). User is back to UC1, or forced enrollment if MFA is enforced. |

## Scope

**In scope**

- Provider abstraction and registry, with TOTP and External OTP providers
- Two-step login flow (password, then second factor) on the REST API
- User endpoints to enroll and disable a method
- Admin configuration: enforce MFA, configure External OTP, reset a user
- Storage of MFA data, rate limiting and audit logging

**Out of scope**

- Frontend screens (separate spec)
- Other methods (WebAuthn, email, push): only the extension point is delivered
- Managing phone numbers in SOGo: the external service resolves username to recipient
- Recovery codes (admin reset only), DAV / ActiveSync / IMAP (separate auth), per-domain config mechanics (already in SOGo 6)

## Technical design

All MFA logic lives in one `mfa` package: a provider registry, one class per method, and a service that the auth blueprint calls between password check and session creation.

### Provider abstraction

Every method implements the same interface and registers under a stable id (`totp`, `external_otp`). The login flow only talks to this interface, so adding a method means one new class plus its config block.

```python
class MFAProvider(ABC):
    id: str                      # "totp", "external_otp"
    requires_enrollment: bool    # True for both: External OTP confirms with one challenge

    def is_available_for(self, user) -> bool: ...
    def begin_enrollment(self, user) -> dict: ...          # TOTP: secret + otpauth URI
    def confirm_enrollment(self, user, code: str) -> bool: ...
    def start_challenge(self, user) -> Challenge: ...      # External OTP: send code or trigger
    def verify(self, user, challenge: Challenge, code: str) -> bool: ...

REGISTRY: dict[str, MFAProvider] = {}   # filled at app start
```

- **TOTP** follows RFC 6238: SHA-1, 6 digits, 30 s period, Â±1 step window (use `pyotp`). `start_challenge` is a no-op.
- **External OTP** has two modes, described under Configuration. In **send** mode, SOGo generates the code with `secrets`, stores its hash in the challenge and checks it locally. In **validate** mode, SOGo stores no code and asks the external service whether the typed code is valid.

### Data model

Each user's MFA method is a JSON object in the `mfa_method` column of `sogo6_user_profiles` (jsonb on PostgreSQL, text on MariaDB). It sits on the user's own profile row, so it needs no user id, and it stays out of the preferences payload sent to the frontend. An empty value means the user has no method.

| Field | Type | Notes |
| --- | --- | --- |
| `provider` | string | `totp`, `external_otp`â€¦ |
| `secret` | string | TOTP only. Encrypted with a key derived from `SOGO_P_VOUCHER_SECRET` (Fernet token) |
| `created_at`, `last_used_at` | ISO 8601 string |  |

```json
{ "provider": "totp", "secret": "gAAAAABn...", "created_at": "2026-11-16T10:02:00Z", "last_used_at": "2026-11-16T14:30:12Z" }
```

There is no `status` field. An enrollment that isn't confirmed yet lives only in Redis, and the column is written once the first code is valid, so whatever is in `mfa_method` is active.

Everything short-lived lives in **Redis**, with a TTL so nothing needs cleaning up:

| Key | Content | TTL |
| --- | --- | --- |
| `mfa:session:<id>` | The MFA session (see API endpoints). Hash: `user`, `stage` (`verify` or `enroll`), `provider`, `code_hash` (External OTP send mode only, HMAC-SHA256 of the code), `attempts` | 300 s |
| `mfa:enroll:<user>` | Pending enrollment: provider and encrypted TOTP secret, or the External OTP test challenge | 600 s |
| `mfa:totp_used:<user>:<step>` | Marks a TOTP step as used (replay protection) | 90 s |
| `mfa:rl:user:<user>`, `mfa:rl:ip:<ip>` | Rate-limit counters | Per window |

The login challenge lives inside the MFA session, so there is no separate challenge key. `attempts` is incremented with `HINCRBY`; the session is deleted on success or at the 5th failure, in both modes, and the user has to log in again.

### Configuration

Admin settings live in the existing settings columns: `settings_domain_default` in `sogo6_settings` for the global default, and `settings_domain` in `sogo6_domain_settings` for a domain, which overrides the default. The MFA block below sits in that JSON. Every write is validated against a schema and refused with 400 if invalid, so a bad value never reaches the login flow. Workers read the settings through a short cache (e.g. 30 s), so a change applies without restart. The TOTP encryption key is not part of these settings: it comes from the `SOGO_P_VOUCHER_SECRET` environment variable. Key names are a proposal.

```json
{
  "allowed_methods": ["totp", "external_otp"],
  "enforced": true,
  "totp": { "issuer": "SOGo" },
  "external_otp": {
    "mode": "validate",
    "timeout_seconds": 5,
    "send_request": null,
    "validate_request": {
      "method": "POST",
      "url": "https://mfa.example.com/validate/check",
      "headers": { "Authorization": "Bearer <token>" },
      "body_format": "form",
      "body": { "user": "{username}", "pass": "{code}" },
      "success": { "status": [200], "json_path": "result.value", "equals": true }
    }
  }
}
```

`allowed_methods` stands for the existing SOGo 6 parameter; use its real name and location. An empty list means MFA is off, and `enforced: true` with an empty list is refused. The `external_otp` block is required only when `external_otp` is allowed.

#### External OTP modes and requests

Each request is a template: `method`, `url`, optional `headers`, `query`, `body_format` (`json`, `form` or `none`) and `body`. Any string value can hold placeholders, and the `success` rule says how to read the answer.

| Mode | `send_request` | `validate_request` | Who checks the code |
| --- | --- | --- | --- |
| `send` | Required. Called at challenge with `{code}` (e.g. SMS text) | Not used | SOGo, against the hash in Redis |
| `validate` | Optional. Called at challenge as a trigger (e.g. MFA server sends its SMS) | Required. Called at verify with the typed `{code}` | The external service, via the `success` rule |

- **Placeholders:** `{code}` is filled by SOGo. All others come from the admin setting `US_MAPPING`, a dict whose keys are the placeholders (e.g. `username`, `email`) and whose values are the user-source fields (e.g. LDAP attributes) they read. A placeholder that is neither `{code}` nor a `US_MAPPING` key is refused when the config is saved.
- **Encoding:** placeholders are substituted inside each parsed value, then encoded by `requests` (`params=`, `json=`, `data=`). The URL and body are never built by string concatenation, so a username can't break the request.
- **Success rule:** `status` (list of accepted HTTP codes) is required; `json_path` + `equals` are optional for APIs that return 200 with a failure in the body. Anything else counts as failure.

A minimal send-mode request for an SMS gateway:

```json
"external_otp": {
  "mode": "send",
  "send_request": {
    "method": "POST",
    "url": "https://sms.example.com/send",
    "body_format": "json",
    "body": { "to": "{username}", "text": "Your SOGo code: {code}" },
    "success": { "status": [200, 201, 202] }
  }
}
```

Most SMS gateways expect a phone number, not a username. SOGo doesn't manage phone numbers, so the admin either points `send_request` at a service that resolves the username, or puts a small relay in front of the gateway.

### TOTP flow

TOTP turns a shared secret and the current time into a 6-digit code. The phone app and the server compute the same code independently, so nothing travels between them after enrollment.

#### How a code is computed (RFC 6238)

1. **Secret:** 20 random bytes (160 bits), base32-encoded to 32 characters. Shared once, through the QR code.
2. **Counter:** `step = floor(unix_time / 30)`, so the code changes every 30 s.
3. **HMAC:** HMAC-SHA1 of the step (8 bytes, big-endian) with the secret as key.
4. **Truncation:** take 4 bytes at an offset given by the last byte of the HMAC, drop the top bit, keep the last 6 decimal digits.

For understanding only (the code uses `pyotp`, which does exactly this):

```python
import base64, hashlib, hmac, struct

def totp_at(secret_b32: str, step: int, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32)
    mac = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)
```

#### Enrollment: secret and QR code

`POST /me/mfa`, when the method that applies is TOTP, generates the secret, keeps it encrypted in Redis under `mfa:enroll:<user>` for 10 min, and returns the `otpauth://` URI. Nothing is written to the profile yet. That URI is what the QR code contains; authenticator apps (Google Authenticator, FreeOTP, Aegisâ€¦) read it directly.

```python
import json
import pyotp

def begin_enrollment(user):
    secret = pyotp.random_base32(32)                 # 160-bit secret
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name=settings.totp.issuer)
    # otpauth://totp/SOGo:alice%40example.com?secret=JBSWY3DP...&issuer=SOGo
    pending = {"provider": "totp",
               "secret": fernet.encrypt(secret.encode()).decode()}
    redis.set(f"mfa:enroll:{user.id}", json.dumps(pending), ex=600)
    return {"otpauth_uri": uri, "secret": secret}  # secret shown for manual entry
```

- **QR code:** the frontend renders `otpauth_uri` as a QR code (e.g. `qrcode.react`). Recommended: the backend stays free of image code, and no picture of the secret ends up in caches or logs.
- If a backend image is ever needed, `qrcode` produces a PNG data URI:

```python
import base64, io, qrcode

buf = io.BytesIO()
qrcode.make(uri).save(buf, format="PNG")
qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
```

- The secret is returned in clear in this one response only, with `Cache-Control: no-store`. Calling the endpoint again replaces the pending enrollment; the user's current method stays in use until the new one is confirmed.

`POST /me/mfa/confirm` checks one code against the pending secret with the same `verify_totp` as login. On success the method is written to `mfa_method`, the Redis enrollment key is deleted, and the code's step is marked as used, so it can't be reused to log in.

#### Verification at login

`pyotp.TOTP.verify(code, valid_window=1)` checks the Â±30 s window but doesn't say which step matched, which replay protection needs. So we loop over the three steps ourselves and use `pyotp` only to compute each code:

```python
import hmac, time
import pyotp

PERIOD = 30

def verify_totp(user, method: dict, code: str) -> bool:
    if not (len(code) == 6 and code.isdigit()):
        return False
    secret = fernet.decrypt(method["secret"].encode()).decode()
    totp = pyotp.TOTP(secret)
    now = int(time.time()) // PERIOD
    for step in (now - 1, now, now + 1):
        if hmac.compare_digest(totp.at(step * PERIOD), code):
            # atomic: fails if this step was already used, even by a concurrent request
            return bool(redis.set(f"mfa:totp_used:{user.id}:{step}", 1, nx=True, ex=90))
    return False
```

The `SET â€¦ NX` is what makes replay protection hold when two requests submit the same code at the same moment. It keeps the check out of the database, so it behaves the same on PostgreSQL and MariaDB.

Each failed call increments `attempts` on the Redis challenge (5 max). On success, `last_used_at` is updated in `mfa_method`.

### API endpoints

No endpoint takes a method. The backend works out which one applies from the admin settings and the user's profile: with one allowed method there is nothing to choose; with several, it uses the method the user picked in their preferences.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/login` | none | Password check. No MFA: returns the user session. Method set: starts its challenge (External OTP sends the code or calls the trigger; TOTP does nothing) and returns `mfa_required` and the method, with an `mfa_session` at stage `verify`. No method while enforced: returns `enrollment_required` and the allowed methods, with an `mfa_session` at stage `enroll` |
| POST | `/auth/mfa/verify` | `mfa_session` (`verify`) | Checks the code (locally, or via `validate_request`); on success deletes the MFA session and issues the user session |
| POST | `/me/mfa` | user session or `mfa_session` (`enroll`) | Starts setup of the method that applies. TOTP: secret + URI. External OTP: sends a test challenge |
| POST | `/me/mfa/confirm` | user session or `mfa_session` (`enroll`) | Saves the method to `mfa_method` after one valid code; replaces the previous method if any |
| DELETE | `/me/mfa` | user session + current code | Clears `mfa_method` (403 if enforced) |
| PATCH | `/admin/settings/mfa` | admin session | Validates and updates the MFA settings, global or per domain; 400 on invalid values |
| POST | `/admin/settings/mfa/test` | admin session | Sends a test request for a given username and shows the raw answer, so admins can check their templates |
| DELETE | `/admin/users/<id>/mfa` | admin session | Clears the user's `mfa_method` (UC7) |

The frontend never picks a method at login: the backend reads the user's active method and the admin config. There is no resend endpoint; a user who didn't get the code logs in again, which starts a new challenge. Since every valid password now sends an External OTP code, `/auth/login` is rate-limited per user as well as per IP, which also caps SMS costs.

The `mfa_session` is a server-side session, separate from the user session. `/auth/login` creates it after a valid password and sends it as its own cookie (HttpOnly, Secure, SameSite=Strict); its content lives in Redis under `mfa:session:<id>`. From it the backend finds the user id, then their profile and preferences, so the MFA endpoints need no other identifier. It lasts 5 min, gives access to nothing but the endpoints above for its stage (`verify`: `/auth/mfa/verify`; `enroll`: `/me/mfa` and `/me/mfa/confirm`), and is deleted when the user session is issued.

### Login flow

&#91;embedded content: login flow Â· 2 decisions, enrollment branch\]

A user with no active method only reaches this step when MFA is enforced: they enroll first, then verify like everyone else.

## Edge cases, security and caveats

The riskiest part is not TOTP itself but the gaps around it: other login paths, the external call, and brute force.

- **No session before the second factor.** Session cookies and API tokens are created only in `/auth/mfa/verify`. The mfa\_session is never accepted as a user session, and every other endpoint rejects it.
- **Webmail login only.** CalDAV, CardDAV, ActiveSync and IMAP use a separate auth system and are out of scope. SSO logins (SAML, CAS, OIDC) should skip SOGo MFA and rely on the identity provider.
- **Brute force.** Max 5 code attempts per challenge, then the challenge dies. Rate-limit `/auth/mfa/*` per user and per IP. Log every failure. This applies in validate mode too: never rely on the external service to count attempts.
- **TOTP replay and drift.** Each accepted step is marked in Redis with `SET NX` and refused if already there. Accept Â±1 step (Â±30 s); server clocks must be NTP-synced.
- **Constant-time compare** for codes and hashes (`hmac.compare_digest`).
- **Secrets at rest.** TOTP secrets are encrypted with a Fernet key derived (HKDF-SHA256) from `SOGO_P_VOUCHER_SECRET`. Changing that variable makes every stored TOTP secret unreadable and users must enroll again: the admin docs must say so.
- **External service down or unclear answer.** Fail closed: a timeout, a network error, a user unknown to the external service, or an answer that doesn't match the `success` rule is a failure, never a fallback to password-only. Return a distinct error ("code could not be sent" vs "wrong code") so the frontend can tell the user. Respect the timeout so a slow service doesn't block Flask workers.
- **External OTP request safety.** Verify TLS; `https` required by default. Never log the code, request bodies, or headers (they hold API tokens).
- **SMS is a weak factor.** It is exposed to SIM swapping. The admin docs should say TOTP is stronger and SMS suits users who can't use an app.
- **Username format.** Normalise the username (case, domain) the same way everywhere, including the `{username}` value sent out.
- **Enforcement turned on later.** Users without a method get an MFA session at stage enroll at their next login. Existing sessions stay valid until they expire, unless sessions are revoked on enforcement. If the admin removes a user's method from the allowed methods, the user counts as having no method: forced enrollment if MFA is enforced, password only otherwise.
- **Unconfirmed enrollments.** They live only in Redis and vanish after 10 min; the user's current method stays in use meanwhile.
- **Column type.** `mfa_method` is jsonb on PostgreSQL and text on MariaDB. Read and write it through one helper that serialises JSON, never with database-specific JSON operators.
- **Multiple Flask workers.** Challenge state, pending enrollments and rate-limit counters must be shared (Redis), never in process memory.
- **Audit log.** Record enrollment, disable, admin reset, config change, success and failure, with user, IP and method. Never the code or secret.

## Open questions

- [ ] Should enabling enforcement (or switching to External OTP) revoke existing sessions?
- [ ] Forced enrollment with several allowed methods: should the `mfa_session` at stage `enroll` be allowed to save the method choice in the user's preferences, or should `POST /me/mfa` accept the choice in this case only?

## Testing and definition of done

The feature is done when every use case's acceptance criteria pass in automated tests and the items below are checked.

- [ ] Unit tests for TOTP against the RFC 6238 test vectors, including the Â±1 step window and replay refusal
- [ ] Unit tests for the External OTP request builder: each `body_format` Ã— method, placeholders in URL, query, headers and body, and usernames with special characters, with mocked HTTP (`responses`)
- [ ] Placeholder resolution through `US_MAPPING`, including a missing user-source field
- [ ] Success rule tests: accepted and refused status, `json_path` match, mismatch, missing path, non-JSON body
- [ ] Both modes end to end: send (local check) and validate (with and without trigger)
- [ ] External failure cases: timeout, non-success status, network error, all failing closed
- [ ] Integration tests of the full login flow: MFA off, each method opt-in, enforced with and without a method, several allowed methods with the user choosing, and a user whose method is no longer allowed
- [ ] `mfa_method` read and written correctly on PostgreSQL (jsonb) and MariaDB (text)
- [ ] Global settings overridden by domain settings
- [ ] Tests that `mfa_session` is refused on every non-MFA endpoint, never accepted as a user session, and limited to its stage
- [ ] Rate limiting and challenge expiry tested, in both External OTP modes
- [ ] Admin API refuses invalid MFA config (unknown placeholder, missing request for the mode) with a 400 and a clear message
- [ ] Registering a dummy third provider in tests works without touching the login flow
- [ ] API documented (OpenAPI or equivalent) for the frontend team
- [ ] Admin documentation: config keys, `US_MAPPING` placeholders, both modes with an SMS and an MFA-server example, `SOGO_P_VOUCHER_SECRET`, user reset
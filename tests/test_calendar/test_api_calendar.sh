#!/usr/bin/env bash
# SOGo 6 Calendar API - functional test script
#
# Usage:
#   ./test_api_calendar.sh [OPTIONS] [base_url] [username] [password]
#
# Defaults: http://localhost:5000/api/user/v1   sogo-tests1@example.org   sogo

set -euo pipefail

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [base_url] [username] [password]

Functional smoke tests for the SOGo 6 Calendar REST API.

OPTIONS:
  -d          Delete mode: execute all DELETE operations at the end.
              Without this flag, DELETE steps are skipped so you can inspect
              the created data in the database.
  -i          Interactive mode: pause before each test section.
              Press SPACE to continue, Q to quit.
  -h, --help  Show this help message and exit.

POSITIONAL ARGUMENTS:
  base_url    API base URL  (default: http://localhost:5000/api/user/v1)
  username    Test account  (default: sogo-tests1@example.org)
  password    Password      (default: sogo)

EXAMPLES:
  # Batch run, no deletes (inspect DB afterwards)
  ./tfa_tests_sogo_calendar.sh

  # Batch run, clean up everything at the end
  ./tfa_tests_sogo_calendar.sh -d

  # Interactive run against a remote server
  ./tfa_tests_sogo_calendar.sh -d -i https://sogo.example.org/api/user/v1 alice secret

TEST COVERAGE:
   1  Authentication (login, token extraction)
   2  Calendar CRUD (create, list, get, patch)
   3  Simple event CRUD (create, get, patch title / location / categories)
   4  All-day event
   5  Event with attendees and reminders
   6  Recurring events (daily COUNT, weekly BYDAY+UNTIL, monthly BYMONTHDAY)
   7  RRULE expansion - GET with date range returns expanded occurrences
   8  Full-text search
   9  Detached occurrence lifecycle:
        a. POST occurrence with recurrence_id -> separate DB row
        b. GET /events returns the override in expansion (not the original slot)
        c. DELETE occurrence -> slot cancelled via EXDATE, master survives
        d. GET /events no longer returns the cancelled slot
  10  EXDATE via PATCH (recurrence_exceptions added directly to master)
  11  Task CRUD (create, get, patch title / percent_complete, list)
  12  Isolation - tasks absent from GET /events, events absent from GET /tasks
  13  Cross-calendar - GET /events and GET /tasks without calendar key return
      data from all calendars and contain no leaked component type
  14  Error paths (unknown event key, unknown calendar key, override on
      non-recurring event)
  15  FreeBusy:
        a. Setup - LOGIN_2 (America/New_York) and LOGIN_3 (Asia/Tokyo) each create
           a calendar and an event; LOGIN_1 creates 2 events on 2037-06-15
        b. Multi-user JSON: LOGIN_3 queries LOGIN_1 + LOGIN_2 in one call
        c. Cross-user JSON query: LOGIN_3 -> LOGIN_1 (2 busy periods)
        d. Common slot: LOGIN_3 -> LOGIN_2, confirms LOGIN_2 busy at same 14:00 UTC
           slot as LOGIN_1 (scheduling conflict)
        e. No overlap: LOGIN_1 -> LOGIN_3 during 14:00 window -> 0 periods (free)
        f. Cross-tz: LOGIN_1 -> LOGIN_3 at 22:00 UTC -> BUSY (Asia/Tokyo event)
        g. Self-query: LOGIN_2 queries own free/busy
        h. Error - range > 90 days -> S000614
  16  Invitation flow (cross-account):
        a. LOGIN_1 creates an event with LOGIN_2 as attendee
        b. LOGIN_2 immediately sees the event in their own /events list (propagated copy)
        c. LOGIN_2 accepts the invitation via POST /events/{key}/attendance
        d. LOGIN_1 sees ACCEPTED status on their organizer copy
        e. LOGIN_2 declines a second invitation - LOGIN_1 sees DECLINED
  18  Recurrence scope (THISANDFUTURE + single occurrence):
        a. Edit single occurrence - PATCH with recurrence_id -> detached override
        b. THISANDFUTURE split with updates - PATCH with recurrence_id + THISANDFUTURE
           -> original truncated, new master created with correct title
        c. Verify original series truncated: absent from split point, new series present
        d. THISANDFUTURE truncate-only (no updates) -> series truncated, no new master
        e. THISANDFUTURE on COUNT-based series -> new series has UNTIL, not COUNT
        f. Edit occurrence then GET verifies modified title in expansion
        g. Split series then GET verifies new series expands
        h. THISANDFUTURE on non-recurring event -> rejected
        i. DELETE master recurring event -> all occurrences removed
        j. EXDATE on slot without detached override -> slot vanishes from expansion
  19  Conditional DELETE (only when -d is passed, steps 62-64)
  21  External calendars (ICS subscriptions):
        a. Create ICS subscription (POST /external-calendars)
        b. List subscriptions
        c. Get detail, update name/color
        d. Trigger sync (POST /sync) - fetches real Google ICS feed
        e. Verify sync status (GET /sync -> completed)
        f. Synced events visible in GET /events
        g. Write rejected on ICS mirror (read-only)
        h. Delete external calendar
  20  Reminders:
        a. Create event with active reminder (date_start in past, date_end in future)
        b. GET /reminders returns popup + email reminders with event data
        c. GET /reminders?method=popup filters by method
        d. GET /reminders?lookahead=30 extends window
        e. Future event reminder not active
        f. Delete event -> reminders disappear
EOF
    exit 0
}

LOGIN_1="sogo-tests1@example.org"
LOGIN_2="sogo-tests2@example.org"
LOGIN_3="sogo-tests3@example.org"

DEFAULT_BASE_URL="http://localhost:5000/api/user/v1"
DEFAULT_LOGIN="${LOGIN_1}"
DEFAULT_PASSWORD="sogo"

DO_DELETE=false
INTERACTIVE=false

# Handle --help before getopts (getopts does not support long options)
for arg in "$@"; do
    [ "$arg" = "--help" ] && usage
done

while getopts "dih" opt; do
    case $opt in
        d) DO_DELETE=true ;;
        i) INTERACTIVE=true ;;
        h) usage ;;
        *) echo "Unknown option: -$OPTARG  (use -h for help)"; exit 1 ;;
    esac
done
shift $((OPTIND - 1))

BASE="${1:-$DEFAULT_BASE_URL}"
USER="${2:-$DEFAULT_LOGIN}"
PASS="${3:-$DEFAULT_PASSWORD}"

# Fixtures are pinned to a fixed year instead of being computed from today, because the recurrence
# assertions constrain both the weekday (FREQ=WEEKLY;BYDAY=MO,WE,FR expects a Monday start) and the
# day of month (FREQ=MONTHLY;BYMONTHDAY=1 expects the 1st). A single day offset cannot preserve both,
# since months differ in length - so the year is bumped to one whose calendar repeats instead.
#
# Once the clock reaches that year, every "upcoming event" assumption silently inverts: reminder
# activity windows, freebusy baselines and reschedule flows all reason about dates now in the past.
# Rather than fail deep in some step with an unexplained mismatch, stop here. Next matching years
# (June 1st on a Monday, non-leap like 2026): 2043, 2054. Bump every date with: sed -i '' 's/2037/2043/g'
FIXTURE_YEAR=2037
if [ "$(date +%Y%m%d)" -ge "${FIXTURE_YEAR}0601" ]; then
    echo "Fixture dates expired: they are pinned to $FIXTURE_YEAR and the clock has reached that window."
    echo "Bump them to the next year whose calendar matches (2043), see the note above this check."
    exit 1
fi

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m';  RESET='\033[0m'

PASS_COUNT=0; FAIL_COUNT=0

ok()   { echo -e "${GREEN}  [PASS]${RESET} $1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "${RED}  [FAIL]${RESET} $1"; FAIL_COUNT=$((FAIL_COUNT+1)); }
step() {
    echo -e "\n${CYAN}== $1 ==${RESET}"
    if $INTERACTIVE; then
        echo -e "${YELLOW}  Press SPACE to run this section, Q to quit...${RESET}"
        while IFS= read -r -s -n1 key; do
            if [[ "$key" == " " ]]; then break; fi
            if [[ "$key" == "q" || "$key" == "Q" ]]; then
                echo -e "\n${YELLOW}Interrupted.${RESET}"
                echo -e "${CYAN}==================================================${RESET}"
                echo -e "  Results : ${GREEN}$PASS_COUNT passed${RESET}  ${RED}$FAIL_COUNT failed${RESET}"
                echo -e "${CYAN}==================================================${RESET}"
                exit 0
            fi
        done
    fi
}
info() { echo -e "${YELLOW}  ->${RESET} $1"; }
skip() { echo -e "${YELLOW}  [SKIP]${RESET} $1 (run with -d to execute)"; }

SMTP_URL="smtp://localhost:25"

# Injects a raw iMIP message straight into the MTA. The Mail Send API cannot be used for this: its
# schema carries no attachment field, and the outgoing module hardcodes application/octet-stream on
# the parts it builds, so it can never emit the text/calendar part inbound processing looks for.
# Arguments: sender, recipient, subject, iCalendar body.
send_imip_mail() {
    local sender="$1" rcpt="$2" mail_subject="$3" ics_body="$4"
    local raw
    raw=$(mktemp)
    {
        printf 'From: %s\r\n' "$sender"
        printf 'To: %s\r\n' "$rcpt"
        printf 'Subject: %s\r\n' "$mail_subject"
        printf 'MIME-Version: 1.0\r\n'
        printf 'Content-Type: multipart/mixed; boundary="imipbnd"\r\n'
        printf '\r\n--imipbnd\r\n'
        printf 'Content-Type: text/plain; charset=UTF-8\r\n\r\n'
        printf 'Scheduling reply.\r\n'
        printf '\r\n--imipbnd\r\n'
        printf 'Content-Type: text/calendar; method=REPLY; charset=UTF-8\r\n\r\n'
        printf '%b\r\n' "$ics_body"
        printf '%s\r\n' '--imipbnd--'
    } > "$raw"
    curl -s --url "$SMTP_URL" --mail-from "$sender" --mail-rcpt "$rcpt" --upload-file "$raw" >/dev/null 2>&1
    rm -f "$raw"
}

# Builds a METHOD:REPLY VCALENDAR. attendee_lines is passed verbatim so a caller can declare several
# ATTENDEE properties or a SENT-BY parameter.
build_reply_ics() {
    local ics_uid="$1" ics_seq="$2" ics_start="$3" attendee_lines="$4" ics_dtstamp="${5:-$3}"
    printf 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SOGo tests//EN\r\nMETHOD:REPLY\r\nBEGIN:VEVENT\r\nUID:%s\r\nDTSTAMP:%s\r\nDTSTART:%s\r\nSEQUENCE:%s\r\nORGANIZER:mailto:%s\r\n%s\r\nEND:VEVENT\r\nEND:VCALENDAR' \
        "$ics_uid" "$ics_dtstamp" "$ics_start" "$ics_seq" "$LOGIN_1" "$attendee_lines"
}

# Waits for a mail carrying the given subject then opens it, which is what triggers inbound iMIP
# processing. Echoes the mail uid, empty when it never arrived.
open_mail_by_subject() {
    local auth="$1" wanted="$2" found=""
    local i
    for i in $(seq 1 15); do
        req "$BASE/mailboxes/0/folders/INBOX/mails?sort_by=date&sort_order=desc&fields=contents&fields_action=exclude" \
            -H "$auth" >/dev/null
        found=$(body | jq -r --arg s "$wanted" '[.data[]? | select(.subject == $s)][0].uid // empty')
        [ -n "$found" ] && break
        sleep 1
    done
    [ -z "$found" ] && return 1
    req "$BASE/mailboxes/0/folders/INBOX/mails/$found" -H "$auth" >/dev/null
    echo "$found"
}

TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

req() {
    curl -s -o "$TMPFILE" -w "%{http_code}" "$@"
}
body()    { cat "$TMPFILE"; }
extract() { body | jq -r "${1} // empty"; }

check_code() {
    local label="$1" got="$2" want="$3"
    [ "$got" = "$want" ] && ok "$label (HTTP $got)" || fail "$label - expected HTTP $want, got $got"
}
check_error() {
    local label="$1"
    local code; code=$(body | jq -r '.error_code // empty')
    [ "$code" = "S000000" ] && ok "$label (S000000)" || fail "$label - error_code='$code'"
}
check_field() {
    local path="$1" want="$2"
    local got; got=$(body | jq -r "$path // empty")
    [ "$got" = "$want" ] && ok "$path = '$want'" || fail "$path - expected '$want', got '$got'"
}
check_not_empty() {
    local path="$1"
    local got; got=$(body | jq -r "$path // empty")
    [ -n "$got" ] && ok "$path is set ($got)" || fail "$path is empty"
}
check_count() {
    local label="$1" path="$2" want="$3"
    local got; got=$(body | jq -r "$path | length")
    [ "$got" = "$want" ] && ok "$label count=$want" || fail "$label - expected $want, got $got"
}
check_error_code() {
    local label="$1" want="$2"
    local got; got=$(body | jq -r '.error_code // empty')
    [ "$got" = "$want" ] && ok "$label ($want)" || fail "$label - expected error_code $want, got '$got'"
}

if ! command -v jq &>/dev/null; then
    echo "jq is required (brew install jq)"; exit 1
fi

echo ""
echo -e "${CYAN}SOGo 6 Calendar API - functional tests${RESET}"
echo -e "  Base URL : $BASE"
echo -e "  User     : $USER"
echo -e "  Deletes  : $(${DO_DELETE} && echo 'enabled (-d)' || echo 'disabled (omit -d to inspect DB)')"
echo -e "  Mode     : $(${INTERACTIVE} && echo 'interactive (-i)' || echo 'batch')"

# -- 1. LOGIN ------------------------------------------------------------------

step "1. Authentication"
info "Logs in as LOGIN_1 and extracts the JWT token used by all subsequent requests."

CODE=$(req -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}")
check_code "POST /auth/login" "$CODE" "200"

TOKEN=$(extract '.data.jwt_token')
if [ -z "$TOKEN" ]; then
    fail "Could not extract auth token"; echo "Response: $(body)"; exit 1
fi
ok "Token obtained"
info "Token: ${TOKEN:0:40}..."

H_AUTH="Authorization: Bearer $TOKEN"
H_JSON="Content-Type: application/json"

# -- 2. CALENDAR CRUD ---------------------------------------------------------

step "2. Calendar - create"
info "Creates a fresh calendar that will hold all events created during this test run."

CODE=$(req -X POST "$BASE/calendars" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "name": "Test Calendar",
        "color": "#3B82F6",
        "description": "Created by functional test script",
        "timezone": "Europe/Paris"
    }')
check_code  "POST /calendars" "$CODE" "201"
check_error "POST /calendars error_code"
check_field ".data.name" "Test Calendar"
CAL_KEY=$(extract '.data.key')
info "Calendar key: $CAL_KEY"

step "3. Calendar - list"
info "Verifies GET /calendars returns at least the newly created calendar (total_count >= 1)."

CODE=$(req "$BASE/calendars" -H "$H_AUTH")
check_code  "GET /calendars" "$CODE" "200"
check_error "GET /calendars error_code"
TOTAL=$(extract '.data.total_count')
info "Total calendars: $TOTAL"
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "total_count >= 1" || fail "total_count=$TOTAL"

step "4. Calendar - get by key"
info "Fetches the calendar by its key and verifies the name is returned correctly."

CODE=$(req "$BASE/calendars/$CAL_KEY" -H "$H_AUTH")
check_code  "GET /calendars/$CAL_KEY" "$CODE" "200"
check_field ".data.name" "Test Calendar"

step "5. Calendar - patch"
info "Renames the calendar and changes its color. Verifies both fields are updated in the response."

CODE=$(req -X PATCH "$BASE/calendars/$CAL_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Test Calendar (renamed)", "color": "#EF4444"}')
check_code  "PATCH /calendars/$CAL_KEY" "$CODE" "200"
check_field ".data.name"  "Test Calendar (renamed)"
check_field ".data.color" "#EF4444"

# -- 3. SIMPLE EVENT CRUD -----------------------------------------------------

step "6. Event - create simple"
info "A regular timed event with categories. Verifies basic CRUD and field round-trip."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Team Meeting",
        "description": "Weekly sync",
        "location": "Room A",
        "date_start": "2037-06-10T09:00:00Z",
        "date_end":   "2037-06-10T10:00:00Z",
        "timezone": "Europe/Paris",
        "status": "confirmed",
        "visibility": "public",
        "show_as": "busy",
        "categories": ["Work", "Meeting"]
    }')
check_code  "POST /events simple" "$CODE" "201"
check_error "POST /events simple error_code"
check_field ".data.title"    "Team Meeting"
check_field ".data.location" "Room A"
EVT_KEY=$(extract '.data.key')
info "Event key: $EVT_KEY"

step "7. Event - get by key"
info "Fetches the event directly by its key. Verifies the title round-trips correctly."

CODE=$(req "$BASE/events/$EVT_KEY" -H "$H_AUTH")
check_code  "GET /events/$EVT_KEY" "$CODE" "200"
check_field ".data.title" "Team Meeting"

step "8. Event - patch title and location"
info "Partially updates an existing event. Only title and location are sent; other fields must be untouched."

CODE=$(req -X PATCH "$BASE/events/$EVT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Team Meeting (updated)", "location": "Room B"}')
check_code  "PATCH /events title+location" "$CODE" "200"
check_field ".data.title"    "Team Meeting (updated)"
check_field ".data.location" "Room B"

step "9. Event - patch categories"
info "Replaces the categories array on an existing event. Verifies the new array length is 3."

CODE=$(req -X PATCH "$BASE/events/$EVT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"categories": ["Work", "Meeting", "Q2"]}')
check_code "PATCH /events categories" "$CODE" "200"
check_count "categories" ".data.categories" "3"

# -- 4. ALL-DAY + COMPLEX EVENTS ----------------------------------------------

step "10. Event - create all-day"
info "An all-day event. Verifies that all_day=true is stored and returned correctly."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Company Holiday",
        "date_start": "2037-07-14T00:00:00Z",
        "date_end":   "2037-07-14T23:59:59Z",
        "all_day": true,
        "visibility": "public"
    }')
check_code  "POST /events all-day" "$CODE" "201"
check_field ".data.all_day" "true"
ALLDAY_KEY=$(extract '.data.key')

step "11. Event - create with attendees and reminders"
info "Event with organizer, two attendees (required/optional) and two reminders (popup/email)."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Project Kickoff",
        "location": "Conf Room B",
        "date_start": "2037-06-15T14:00:00Z",
        "date_end":   "2037-06-15T15:30:00Z",
        "timezone": "Europe/Paris",
        "organizer": {"email": "organizer@example.org", "name": "Alice"},
        "attendees": [
            {"email": "bob@example.org",   "name": "Bob",   "role": "required", "status": "needs-action", "rsvp": true,  "cutype": "individual"},
            {"email": "carol@example.org", "name": "Carol", "role": "optional", "status": "accepted",     "rsvp": false, "cutype": "individual"}
        ],
        "reminders": [
            {"method": "popup", "minutes_before": 15},
            {"method": "email", "minutes_before": 60}
        ],
        "categories": ["Project", "Important"]
    }')
check_code  "POST /events with attendees" "$CODE" "201"
check_error "POST /events with attendees error_code"
check_count "attendees" ".data.attendees" "2"
check_count "reminders" ".data.reminders" "2"
COMPLEX_KEY=$(extract '.data.key')

# -- 5. RECURRING EVENTS -------------------------------------------------------

step "12. Event - recurring daily (COUNT=5)"
info "Creates a VEVENT with RRULE:FREQ=DAILY;COUNT=5. Verifies the rule is stored correctly."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Daily Standup",
        "date_start": "2037-06-01T09:00:00Z",
        "date_end":   "2037-06-01T09:15:00Z",
        "timezone": "Europe/Paris",
        "recurrence_rule": {"frequency": "daily", "count": 5, "interval": 1}
    }')
check_code  "POST /events daily" "$CODE" "201"
check_error "POST /events daily error_code"
check_field ".data.recurrence_rule.frequency" "daily"
DAILY_KEY=$(extract '.data.key')
DAILY_UID=$(extract '.data.uid')
info "Daily event key: $DAILY_KEY  uid: $DAILY_UID"

step "13. Event - recurring weekly MO/WE/FR with UNTIL"
info "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=... Verifies by_day array length."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Cardio Session",
        "date_start": "2037-06-01T07:00:00Z",
        "date_end":   "2037-06-01T08:00:00Z",
        "timezone": "Europe/Paris",
        "recurrence_rule": {
            "frequency": "weekly",
            "interval": 1,
            "by_day": ["MO", "WE", "FR"],
            "until": "2037-07-31T23:59:59Z"
        }
    }')
check_code  "POST /events weekly MO/WE/FR" "$CODE" "201"
check_count "by_day" ".data.recurrence_rule.by_day" "3"
WEEKLY_KEY=$(extract '.data.key')

step "14. Event - recurring monthly BYMONTHDAY=1"
info "RRULE:FREQ=MONTHLY;BYMONTHDAY=1;COUNT=6"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Monthly Review",
        "date_start": "2037-06-01T10:00:00Z",
        "date_end":   "2037-06-01T11:00:00Z",
        "timezone": "Europe/Paris",
        "recurrence_rule": {
            "frequency": "monthly",
            "interval": 1,
            "by_month_day": [1],
            "count": 6
        }
    }')
check_code  "POST /events monthly" "$CODE" "201"
check_field ".data.recurrence_rule.frequency" "monthly"
MONTHLY_KEY=$(extract '.data.key')

# -- 6. RRULE EXPANSION --------------------------------------------------------

step "15. RRULE expansion - daily event over its full range"
info "The daily event has COUNT=5 starting 2037-06-01. A GET over June 1-5 should expand it
  into 5 occurrences. We verify total_count >= 5 and that 'Daily Standup' appears 5 times."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-05T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events June 1-5 (daily expansion)" "$CODE" "200"
check_error "GET /events June 1-5 error_code"
TOTAL=$(extract '.data.total_count')
info "Events in June 1-5: $TOTAL"
[ "$TOTAL" -ge 5 ] 2>/dev/null && ok "total_count >= 5 (daily expansion)" || fail "total_count=$TOTAL (expected >= 5)"
FOUND=$(body | jq -r '[.data.events[] | select(.title == "Daily Standup")] | length')
[ "$FOUND" -ge 5 ] 2>/dev/null && ok "Daily Standup appears $FOUND times" || fail "Daily Standup appears $FOUND times (expected >= 5)"

# Verify that expanded occurrences carry the master's recurrence_rule
FIRST_OCC_FREQ=$(body | jq -r '[.data.events[] | select(.title == "Daily Standup")][0].recurrence_rule.frequency // empty')
[ "$FIRST_OCC_FREQ" = "daily" ] \
    && ok "expanded occurrence carries recurrence_rule.frequency=daily" \
    || fail "expanded occurrence recurrence_rule.frequency='$FIRST_OCC_FREQ' (expected 'daily')"
FIRST_OCC_RECID=$(body | jq -r '[.data.events[] | select(.title == "Daily Standup")][0].recurrence_id // empty')
[ -n "$FIRST_OCC_RECID" ] \
    && ok "expanded occurrence has recurrence_id set ($FIRST_OCC_RECID)" \
    || fail "expanded occurrence has no recurrence_id"

step "16. RRULE expansion - weekly event over two months"
info "The weekly MO/WE/FR event runs from 2037-06-01 to 2037-07-31. June has ~13 occurrences.
  We verify >= 10 for the June window."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events June (weekly expansion)" "$CODE" "200"
FOUND=$(body | jq -r '[.data.events[] | select(.title == "Cardio Session")] | length')
info "Cardio Session occurrences in June: $FOUND"
[ "$FOUND" -ge 10 ] 2>/dev/null && ok "Cardio Session appears >= 10 times in June" || fail "Cardio Session appears $FOUND times (expected >= 10)"

step "17. RRULE expansion - monthly event UNTIL count boundary"
info "Monthly event starts 2037-06-01 with COUNT=6. July 1 is the second occurrence.
  We check that it appears in a July 1 query."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-07-01T00:00:00Z&end_date_time=2037-07-01T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events July 1 (monthly expansion)" "$CODE" "200"
FOUND=$(body | jq -r '[.data.events[] | select(.title == "Monthly Review")] | length')
[ "$FOUND" -ge 1 ] 2>/dev/null && ok "Monthly Review appears on July 1" || fail "Monthly Review does not appear on July 1 (found $FOUND)"

step "18. RRULE - patch recurrence rule (replace COUNT with UNTIL)"
info "Replaces the daily event RRULE to use an UNTIL date instead of COUNT."

CODE=$(req -X PATCH "$BASE/events/$DAILY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "recurrence_rule": {
            "frequency": "daily",
            "interval": 1,
            "until": "2037-06-15T23:59:59Z"
        }
    }')
check_code "PATCH /events recurrence_rule" "$CODE" "200"
UNTIL=$(extract '.data.recurrence_rule.until')
[ -n "$UNTIL" ] && ok "recurrence_rule.until set ($UNTIL)" || fail "recurrence_rule.until is empty"

# -- 7. DETACHED OCCURRENCE LIFECYCLE -----------------------------------------

step "19. Detached occurrence - create override for 2037-06-03"
info "POSTs a detached occurrence for the daily event: same uid, recurrence_id=2037-06-03T09:00:00Z.
  This represents 'move/edit only the June 3rd occurrence of Daily Standup'.
  The API stores this as a separate DB row sharing the master's uid (RECURRENCE-ID override)."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$DAILY_UID\",
        \"title\": \"Daily Standup (June 3 override)\",
        \"date_start\": \"2037-06-03T10:00:00Z\",
        \"date_end\":   \"2037-06-03T10:30:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"recurrence_id\": \"2037-06-03T09:00:00Z\"
    }")
check_code  "POST /events detached occurrence" "$CODE" "201"
check_error "POST /events detached occurrence error_code"
check_field ".data.title" "Daily Standup (June 3 override)"
RECID=$(extract '.data.recurrence_id' | sed 's/\.000Z$/Z/')
[ "$RECID" = "2037-06-03T09:00:00Z" ] \
    && ok ".data.recurrence_id = '2037-06-03T09:00:00Z'" \
    || fail ".data.recurrence_id - expected '2037-06-03T09:00:00Z', got '$RECID'"
OCCURRENCE_KEY=$(extract '.data.key')
info "Occurrence key: $OCCURRENCE_KEY"

step "20. Detached occurrence - GET expansion shows override, not original slot"
info "When expanding over June 3, the response must include the overridden occurrence
  (10:00-10:30, '...June 3 override') instead of the original 09:00 slot."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-03T00:00:00Z&end_date_time=2037-06-03T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events June 3 (with override)" "$CODE" "200"
check_error "GET /events June 3 error_code"
OVERRIDE_COUNT=$(body | jq -r '[.data.events[] | select(.title == "Daily Standup (June 3 override)")] | length')
ORIGINAL_COUNT=$(body | jq -r '[.data.events[] | select(.title == "Daily Standup" and .recurrence_id == null)] | length')
[ "$OVERRIDE_COUNT" -ge 1 ] 2>/dev/null \
    && ok "Override occurrence appears in expansion ($OVERRIDE_COUNT)" \
    || fail "Override occurrence not found in expansion (count=$OVERRIDE_COUNT)"
[ "$ORIGINAL_COUNT" -eq 0 ] 2>/dev/null \
    && ok "Original slot not duplicated (count=$ORIGINAL_COUNT)" \
    || fail "Original slot still visible alongside override (count=$ORIGINAL_COUNT)"

step "21. Detached occurrence - DELETE cancels the slot (EXDATE)"
info "Deleting a detached occurrence must:
  1. Soft-delete only the detached row (not the master)
  2. Add the recurrence_id to the master's recurrence_exceptions (EXDATE)
  After deletion, the June 3 slot must not appear in the expansion."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/events/$OCCURRENCE_KEY" -H "$H_AUTH")
    check_code  "DELETE /events detached occurrence" "$CODE" "200"
    check_error "DELETE /events detached occurrence error_code"

    CODE=$(req "$BASE/events/$DAILY_KEY" -H "$H_AUTH")
    check_code  "GET master still exists after occurrence delete" "$CODE" "200"
    check_field ".data.title" "Daily Standup"

    CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-03T00:00:00Z&end_date_time=2037-06-03T23:59:59Z" \
        -H "$H_AUTH")
    check_code "GET /events June 3 after occurrence delete" "$CODE" "200"
    SLOT_COUNT=$(body | jq -r "[.data.events[] | select(.uid == \"$DAILY_UID\")] | length")
    [ "$SLOT_COUNT" -eq 0 ] 2>/dev/null \
        && ok "June 3 slot absent from expansion after EXDATE (count=$SLOT_COUNT)" \
        || fail "June 3 slot still visible after deletion (count=$SLOT_COUNT)"

    CODE=$(req "$BASE/events/$DAILY_KEY" -H "$H_AUTH")
    EXDATE_COUNT=$(body | jq -r '.data.recurrence_exceptions | length')
    [ "$EXDATE_COUNT" -ge 1 ] 2>/dev/null \
        && ok "Master recurrence_exceptions has $EXDATE_COUNT entry(ies)" \
        || fail "Master recurrence_exceptions is still empty after occurrence delete"
else
    skip "DELETE detached occurrence + EXDATE verification (step 21)"
    info "Keys to inspect: occurrence=$OCCURRENCE_KEY  master=$DAILY_KEY  uid=$DAILY_UID"
fi

# -- 8. EXDATE VIA PATCH -------------------------------------------------------

step "22. EXDATE via PATCH - cancel a specific date on the weekly event"
info "PATCHes the weekly MO/WE/FR event to add 2037-06-03T07:00:00Z to recurrence_exceptions.
  A subsequent GET for that slot must not return the weekly event."

CODE=$(req -X PATCH "$BASE/events/$WEEKLY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"recurrence_exceptions": ["2037-06-03T07:00:00Z"]}')
check_code  "PATCH /events add recurrence_exceptions" "$CODE" "200"
EXDATES=$(extract '.data.recurrence_exceptions | length')
[ "$EXDATES" -ge 1 ] 2>/dev/null \
    && ok "recurrence_exceptions count >= 1 after patch ($EXDATES)" \
    || fail "recurrence_exceptions empty after patch"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-03T07:00:00Z&end_date_time=2037-06-03T07:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events June 3 07:xx after EXDATE patch" "$CODE" "200"
CARDIO_COUNT=$(body | jq -r '[.data.events[] | select(.title == "Cardio Session")] | length')
[ "$CARDIO_COUNT" -eq 0 ] 2>/dev/null \
    && ok "Cardio Session absent for the EXDATEd slot" \
    || fail "Cardio Session still visible for EXDATEd slot (count=$CARDIO_COUNT)"

# -- 9. LIST AND SEARCH --------------------------------------------------------

step "23. Events - list over June date range (no tasks)"
info "Only VEVENT components must appear; tasks created later must be absent."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events?start..end June" "$CODE" "200"
check_error "GET /events date range error_code"
TOTAL=$(extract '.data.total_count')
info "Events in June: $TOTAL"
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "total_count >= 1" || fail "total_count=$TOTAL"

step "24. Events - full-text search"
info "Searches events by title keyword 'Standup'. The daily recurring event must appear; at least 1 result expected."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=Standup" -H "$H_AUTH")
check_code  "GET /events?search=Standup" "$CODE" "200"
check_error "GET /events search error_code"
TOTAL=$(extract '.data.total_count')
info "Search 'Standup' -> $TOTAL result(s)"
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "search returned >= 1 result" || fail "search returned $TOTAL results"

step "24b. Events - search behaviors (prefix, accents, no-match, hostile input)"
info "Creates an accented event, then verifies prefix matching (as-you-type), accent-insensitive
      search in both directions, an empty result on a no-match query, and that hostile input is
      sanitized (200, zero result, table intact)."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Réunion Café",
        "location": "Hôtel Joël",
        "date_start": "2037-06-12T14:00:00Z",
        "date_end":   "2037-06-12T15:00:00Z"
    }')
check_code "POST /events accented" "$CODE" "201"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=Standu" -H "$H_AUTH")
check_code "GET /events?search=Standu (prefix)" "$CODE" "200"
TOTAL=$(extract '.data.total_count')
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "prefix 'Standu' matches 'Standup'" || fail "prefix 'Standu' returned $TOTAL result(s)"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=reunion" -H "$H_AUTH")
check_code "GET /events?search=reunion (unaccented query)" "$CODE" "200"
TOTAL=$(extract '.data.total_count')
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "'reunion' matches 'Réunion'" || fail "'reunion' returned $TOTAL result(s)"

# Accented query against accented data ("Joël" lives in the event location)
CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=Jo%C3%ABl" -H "$H_AUTH")
check_code "GET /events?search=Joël (accented query)" "$CODE" "200"
TOTAL=$(extract '.data.total_count')
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "'Joël' matches event location" || fail "'Joël' returned $TOTAL result(s)"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=zzzqqqxx" -H "$H_AUTH")
check_code "GET /events?search=zzzqqqxx (no match)" "$CODE" "200"
TOTAL=$(extract '.data.total_count')
[ "$TOTAL" = "0" ] && ok "no-match query returns 0 result" || fail "no-match query returned $TOTAL result(s)"

# Hostile input: must be reduced to harmless search words (200, no result, no SQL error)
INJ="%27%3B%20DROP%20TABLE%20sogo_calendar_events%3B%20--"
CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=$INJ" -H "$H_AUTH")
check_code "GET /events?search=<sql injection>" "$CODE" "200"
TOTAL=$(extract '.data.total_count')
[ "$TOTAL" = "0" ] && ok "hostile input returns 0 result" || fail "hostile input returned $TOTAL result(s)"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=Standup" -H "$H_AUTH")
check_code "GET /events after hostile input (table intact)" "$CODE" "200"
TOTAL=$(extract '.data.total_count')
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "events table still answers after hostile input" || fail "events table broken after hostile input"

step "25. Events - no params (defaults to today)"
info "Without query params and no search, the API defaults to today's date range."

CODE=$(req "$BASE/calendars/$CAL_KEY/events" -H "$H_AUTH")
check_code  "GET /events (no params)" "$CODE" "200"
check_error "GET /events (no params) error_code"

# -- 10. TASK CRUD -------------------------------------------------------------

step "26. Task - create"
info "Creates a VTODO with a due date and percent_complete. Verifies component_type=task."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/tasks" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Write release notes",
        "description": "Document all changes for v1.0",
        "date_due": "2037-06-30T17:00:00Z",
        "percent_complete": 0,
        "categories": ["Dev", "Docs"]
    }')
check_code  "POST /tasks create" "$CODE" "201"
check_error "POST /tasks create error_code"
check_field ".data.title"          "Write release notes"
check_field ".data.component_type" "task"
# 'date_due' must be returned under the 'date_due' key (mapped back from the internal date_end),
# and date_end must NOT leak into the task response.
DUE_OUT=$(body | jq -r '.data.date_due // empty')
echo "$DUE_OUT" | grep -q "2037-06-30T17:00:00" && ok "task 'date_due' returned (not 'date_end')" || fail "task date_due wrong/missing: '$DUE_OUT'"
[ "$(body | jq -r '.data.date_end // "ABSENT"')" = "ABSENT" ] && ok "task response has no 'date_end'" || fail "task response still exposes 'date_end'"
TASK_KEY=$(extract '.data.key')
info "Task key: $TASK_KEY"

step "27. Task - get by key"
info "Fetches the task by its key. Verifies component_type=task and title round-trip."

CODE=$(req "$BASE/tasks/$TASK_KEY" -H "$H_AUTH")
check_code  "GET /tasks/$TASK_KEY" "$CODE" "200"
check_error "GET /tasks get error_code"
check_field ".data.title"          "Write release notes"
check_field ".data.component_type" "task"
DUE_GET=$(body | jq -r '.data.date_due // empty')
echo "$DUE_GET" | grep -q "2037-06-30T17:00:00" && ok "task 'date_due' round-trips on GET" || fail "task date_due on GET: '$DUE_GET'"


step "27b. Task - create without due returns null due"
info "A VTODO created without a due date must return due=null."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/tasks" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Task without a due date"}')
check_code  "POST /tasks (no due)" "$CODE" "201"
NODUE=$(body | jq -r '.data.date_due')
[ "$NODUE" = "null" ] && ok "task without due -> date_due is null" || fail "task without due -> date_due='$NODUE' (expected null)"
[ "$(body | jq -r '.data.date_end // "ABSENT"')" = "ABSENT" ] && ok "no-due task has no 'date_end'" || fail "no-due task exposes 'date_end'"


step "28. Task - patch title and percent_complete"
info "Marks the task as 100% complete and renames it. Verifies both fields in the response."

CODE=$(req -X PATCH "$BASE/tasks/$TASK_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Write release notes (done)", "percent_complete": 100}')
check_code  "PATCH /tasks title+percent_complete" "$CODE" "200"
check_field ".data.title"            "Write release notes (done)"
check_field ".data.percent_complete" "100"

step "29. Task - create a second task for list/isolation checks"
info "Creates a second task so the list endpoint and isolation tests have at least 2 tasks to assert against."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/tasks" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Review PR #42",
        "date_due": "2037-06-20T12:00:00Z",
        "percent_complete": 50
    }')
check_code  "POST /tasks second task" "$CODE" "201"
TASK_KEY2=$(extract '.data.key')
info "Second task key: $TASK_KEY2"

step "30. Task - list (GET /calendars/{key}/tasks)"
info "Lists tasks for the calendar. Both tasks must appear; no events."

CODE=$(req "$BASE/calendars/$CAL_KEY/tasks?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /tasks list" "$CODE" "200"
check_error "GET /tasks list error_code"
TASK_TOTAL=$(extract '.data.total_count')
info "Tasks in calendar (June): $TASK_TOTAL"
[ "$TASK_TOTAL" -ge 2 ] 2>/dev/null && ok "task list total_count >= 2" || fail "task list total_count=$TASK_TOTAL (expected >= 2)"
COMPONENT_TYPES=$(body | jq -r '[.data.tasks[].component_type] | unique | .[]')
[ "$COMPONENT_TYPES" = "task" ] \
    && ok "all items in task list have component_type=task" \
    || fail "unexpected component_type(s) in task list: $COMPONENT_TYPES"

# -- 11. ISOLATION - tasks/events do not bleed across endpoints ----------------

step "31. Isolation - tasks absent from GET /events"
info "The two tasks just created must not appear in the event list."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events (isolation check)" "$CODE" "200"
TASK_IN_EVENTS=$(body | jq -r '[.data.events[] | select(.component_type == "task")] | length')
[ "$TASK_IN_EVENTS" -eq 0 ] 2>/dev/null \
    && ok "no task found in GET /events (isolation OK)" \
    || fail "GET /events returned $TASK_IN_EVENTS task(s) - isolation broken"

step "32. Isolation - events absent from GET /tasks"
info "The events created earlier must not appear in the task list."

CODE=$(req "$BASE/calendars/$CAL_KEY/tasks?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /tasks (isolation check)" "$CODE" "200"
EVENT_IN_TASKS=$(body | jq -r '[.data.tasks[] | select(.component_type == "event" or .component_type == null)] | length')
[ "$EVENT_IN_TASKS" -eq 0 ] 2>/dev/null \
    && ok "no event found in GET /tasks (isolation OK)" \
    || fail "GET /tasks returned $EVENT_IN_TASKS event(s) - isolation broken"

# -- 12. CROSS-CALENDAR (no calendar key) -------------------------------------

step "33. GET /events - all calendars (no calendar key)"
info "GET /events without a calendar key must return events from all user calendars.
  The test calendar already has several events; the response must include at least one."

CODE=$(req "$BASE/events?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events (no calendar key)" "$CODE" "200"
check_error "GET /events (no calendar key) error_code"
CROSS_EVT_TOTAL=$(extract '.data.total_count')
info "Events (all calendars, June): $CROSS_EVT_TOTAL"
[ "$CROSS_EVT_TOTAL" -ge 1 ] 2>/dev/null \
    && ok "GET /events total_count >= 1 across all calendars" \
    || fail "GET /events returned $CROSS_EVT_TOTAL events (expected >= 1)"
TASK_LEAK=$(body | jq -r '[.data.events[] | select(.component_type == "task")] | length')
[ "$TASK_LEAK" -eq 0 ] 2>/dev/null \
    && ok "GET /events contains no tasks" \
    || fail "GET /events leaked $TASK_LEAK task(s)"

step "34. GET /tasks - all calendars (no calendar key)"
info "GET /tasks without a calendar key must return tasks from all user calendars."

CODE=$(req "$BASE/tasks?start_date_time=2037-06-01T00:00:00Z&end_date_time=2037-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /tasks (no calendar key)" "$CODE" "200"
check_error "GET /tasks (no calendar key) error_code"
CROSS_TASK_TOTAL=$(extract '.data.total_count')
info "Tasks (all calendars, June): $CROSS_TASK_TOTAL"
[ "$CROSS_TASK_TOTAL" -ge 2 ] 2>/dev/null \
    && ok "GET /tasks total_count >= 2 across all calendars" \
    || fail "GET /tasks returned $CROSS_TASK_TOTAL tasks (expected >= 2)"
EVENT_LEAK=$(body | jq -r '[.data.tasks[] | select(.component_type == "event")] | length')
[ "$EVENT_LEAK" -eq 0 ] 2>/dev/null \
    && ok "GET /tasks contains no events" \
    || fail "GET /tasks leaked $EVENT_LEAK event(s)"

# -- 13. ERROR PATHS -----------------------------------------------------------

step "35. Error paths - unknown keys"
info "GET on a non-existent event key must return 404 + S000605. GET on a non-existent calendar key must return 404 + S000602."

CODE=$(req "$BASE/events/nonexistent-key-xyz" -H "$H_AUTH")
check_code "GET /events/nonexistent" "$CODE" "404"
ERR=$(extract '.error_code')
[ "$ERR" = "S000605" ] && ok "unknown event key -> S000605" || fail "unknown event key -> $ERR (expected S000605)"

CODE=$(req "$BASE/calendars/nonexistent-cal-xyz" -H "$H_AUTH")
check_code "GET /calendars/nonexistent" "$CODE" "404"
ERR=$(extract '.error_code')
[ "$ERR" = "S000602" ] && ok "unknown calendar key -> S000602" || fail "unknown calendar key -> $ERR (expected S000602)"

step "36. Error paths - detached occurrence on non-recurring event"
info "Posting a recurrence_id against a non-recurring event must be rejected (not 201)."

EVT_UID=$(curl -s "$BASE/events/$EVT_KEY" -H "$H_AUTH" | jq -r '.data.uid // empty')
CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$EVT_UID\",
        \"title\": \"Bad override\",
        \"date_start\": \"2037-06-10T09:00:00Z\",
        \"date_end\":   \"2037-06-10T10:00:00Z\",
        \"recurrence_id\": \"2037-06-10T09:00:00Z\"
    }")
[ "$CODE" != "201" ] \
    && ok "non-recurring override rejected (HTTP $CODE)" \
    || fail "non-recurring override incorrectly accepted (HTTP 201)"

# -- 15. FREEBUSY --------------------------------------------------------------
#
# Timeline for 2037-06-15 (UTC):
#   LOGIN_1 (Europe/Paris)    : BUSY 09:00-10:00, BUSY 14:00-15:00
#   LOGIN_2 (America/New_York): BUSY 14:00-15:00           <- common slot with LOGIN_1
#   LOGIN_3 (Asia/Tokyo)      : BUSY 22:00-23:00           <- no overlap with LOGIN_1/LOGIN_2
#
# Tests:
#   - cross-user query (LOGIN_3 -> LOGIN_1, LOGIN_3 -> LOGIN_2)
#   - common busy slot confirmed on both sides
#   - slot where one is free while the other is busy
#   - self-query
#   - .ifb endpoint
#   - range-too-large error

step "37. FreeBusy setup - authenticate LOGIN_2 and LOGIN_3"
info "Obtains JWT tokens for LOGIN_2 (America/New_York) and LOGIN_3 (Asia/Tokyo) used in all FreeBusy queries below."

CODE=$(req -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$LOGIN_2\",\"password\":\"$DEFAULT_PASSWORD\"}")
check_code "POST /auth/login (LOGIN_2)" "$CODE" "200"
TOKEN_2=$(extract '.data.jwt_token')
[ -n "$TOKEN_2" ] && ok "LOGIN_2 token obtained" || { fail "Could not extract LOGIN_2 token"; exit 1; }
H_AUTH_2="Authorization: Bearer $TOKEN_2"

CODE=$(req -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$LOGIN_3\",\"password\":\"$DEFAULT_PASSWORD\"}")
check_code "POST /auth/login (LOGIN_3)" "$CODE" "200"
TOKEN_3=$(extract '.data.jwt_token')
[ -n "$TOKEN_3" ] && ok "LOGIN_3 token obtained" || { fail "Could not extract LOGIN_3 token"; exit 1; }
H_AUTH_3="Authorization: Bearer $TOKEN_3"

step "38. FreeBusy setup - LOGIN_1 adds 2 events on 2037-06-15 (Europe/Paris)"
info "09:00-10:00 UTC and 14:00-15:00 UTC. The 14:00 slot will be the common slot with LOGIN_2."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Morning (L1)",
        "date_start": "2037-06-15T09:00:00Z",
        "date_end":   "2037-06-15T10:00:00Z",
        "timezone": "Europe/Paris",
        "show_as": "busy"
    }')
check_code "POST /events FB Morning L1" "$CODE" "201"
FB_L1_MORNING=$(extract '.data.key')

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Afternoon (L1)",
        "date_start": "2037-06-15T14:00:00Z",
        "date_end":   "2037-06-15T15:00:00Z",
        "timezone": "Europe/Paris",
        "show_as": "busy"
    }')
check_code "POST /events FB Afternoon L1" "$CODE" "201"
FB_L1_AFTERNOON=$(extract '.data.key')

step "39. FreeBusy setup - LOGIN_2 creates calendar (America/New_York) + event at 14:00 UTC"
info "14:00 UTC = 10:00 New_York. Common slot with LOGIN_1."

CODE=$(req -X POST "$BASE/calendars" \
    -H "$H_JSON" -H "$H_AUTH_2" \
    -d '{
        "name": "FB Test Calendar (L2)",
        "timezone": "America/New_York"
    }')
check_code "POST /calendars (LOGIN_2)" "$CODE" "201"
CAL_KEY_2=$(extract '.data.key')
info "LOGIN_2 calendar key: $CAL_KEY_2"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY_2/events" \
    -H "$H_JSON" -H "$H_AUTH_2" \
    -d '{
        "title": "FB Standup (L2)",
        "date_start": "2037-06-15T14:00:00Z",
        "date_end":   "2037-06-15T15:00:00Z",
        "timezone": "America/New_York",
        "show_as": "busy"
    }')
check_code "POST /events FB Standup L2" "$CODE" "201"
FB_L2_EVT=$(extract '.data.key')

step "40. FreeBusy setup - LOGIN_3 creates calendar (Asia/Tokyo) + event at 22:00 UTC"
info "22:00 UTC = 07:00+9 Tokyo. No overlap with LOGIN_1 or LOGIN_2."

CODE=$(req -X POST "$BASE/calendars" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d '{
        "name": "FB Test Calendar (L3)",
        "timezone": "Asia/Tokyo"
    }')
check_code "POST /calendars (LOGIN_3)" "$CODE" "201"
CAL_KEY_3=$(extract '.data.key')
info "LOGIN_3 calendar key: $CAL_KEY_3"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY_3/events" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d '{
        "title": "FB Evening (L3)",
        "date_start": "2037-06-15T22:00:00Z",
        "date_end":   "2037-06-15T23:00:00Z",
        "timezone": "Asia/Tokyo",
        "show_as": "busy"
    }')
check_code "POST /events FB Evening L3" "$CODE" "201"
FB_L3_EVT=$(extract '.data.key')

step "41. FreeBusy - multi-user JSON: LOGIN_3 queries LOGIN_1 + LOGIN_2 in one call"
info "Both attendees must appear in response. LOGIN_1 has 2 events, LOGIN_2 has 1."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\", \"$LOGIN_2\"],
        \"start\": \"2037-06-15T00:00:00Z\",
        \"end\":   \"2037-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy multi-user (JSON)" "$CODE" "200"
check_error "POST /freebusy multi-user error_code"
FB_MULTI_L1=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
FB_MULTI_L2=$(body | jq -r --arg uid "$LOGIN_2" '.data.attendees[$uid].periods | length')
[ "$FB_MULTI_L1" -ge 2 ] 2>/dev/null \
    && ok "multi-user: LOGIN_1 has >= 2 periods" \
    || fail "multi-user: LOGIN_1 has $FB_MULTI_L1 period(s) (expected >= 2)"
[ "$FB_MULTI_L2" -ge 1 ] 2>/dev/null \
    && ok "multi-user: LOGIN_2 has >= 1 period" \
    || fail "multi-user: LOGIN_2 has $FB_MULTI_L2 period(s) (expected >= 1)"

step "42. FreeBusy - cross-user JSON: LOGIN_3 queries LOGIN_1 on 2037-06-15"
info "LOGIN_1 has 2 events (09:00 and 14:00). Both must appear as BUSY."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2037-06-15T00:00:00Z\",
        \"end\":   \"2037-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy L3->L1 (JSON)" "$CODE" "200"
check_error "POST /freebusy L3->L1 error_code"
FB_L1_COUNT=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
info "LOGIN_1 busy periods on 2037-06-15: $FB_L1_COUNT"
[ "$FB_L1_COUNT" -ge 2 ] 2>/dev/null \
    && ok "LOGIN_1 has >= 2 busy periods (morning + afternoon)" \
    || fail "LOGIN_1 busy periods = $FB_L1_COUNT (expected >= 2)"
FB_L1_TYPES=$(body | jq -r --arg uid "$LOGIN_1" '[.data.attendees[$uid].periods[].type] | unique | .[]')
[ "$FB_L1_TYPES" = "busy" ] \
    && ok "all LOGIN_1 periods are type=busy" \
    || fail "unexpected period types for LOGIN_1: $FB_L1_TYPES"

step "43. FreeBusy - common slot: LOGIN_3 queries LOGIN_2 on 2037-06-15"
info "LOGIN_2 has the 14:00 event - same UTC slot as LOGIN_1's afternoon event."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_2\"],
        \"start\": \"2037-06-15T00:00:00Z\",
        \"end\":   \"2037-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy L3->L2 (JSON)" "$CODE" "200"
check_error "POST /freebusy L3->L2 error_code"
FB_L2_COUNT=$(body | jq -r --arg uid "$LOGIN_2" '.data.attendees[$uid].periods | length')
info "LOGIN_2 busy periods on 2037-06-15: $FB_L2_COUNT"
[ "$FB_L2_COUNT" -ge 1 ] 2>/dev/null \
    && ok "LOGIN_2 has >= 1 busy period" \
    || fail "LOGIN_2 busy periods = $FB_L2_COUNT (expected >= 1)"
FB_L2_SLOT=$(body | jq -r --arg uid "$LOGIN_2" '[.data.attendees[$uid].periods[] | select(.start == "20370615T140000Z")] | length')
[ "$FB_L2_SLOT" -ge 1 ] 2>/dev/null \
    && ok "LOGIN_2 is busy at 14:00 UTC (common slot with LOGIN_1 confirmed)" \
    || fail "LOGIN_2 is not busy at 14:00 UTC (expected common slot with LOGIN_1)"

step "44. FreeBusy - no overlap: LOGIN_1 queries LOGIN_3 on 14:00-15:00 UTC"
info "LOGIN_3 has no event at 14:00 UTC - must return 0 busy periods in that window."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_3\"],
        \"start\": \"2037-06-15T14:00:00Z\",
        \"end\":   \"2037-06-15T15:00:00Z\"
    }")
check_code  "POST /freebusy L1->L3 14:00 window" "$CODE" "200"
check_error "POST /freebusy L1->L3 14:00 error_code"
FB_L3_AT14=$(body | jq -r --arg uid "$LOGIN_3" '.data.attendees[$uid].periods | length')
[ "$FB_L3_AT14" -eq 0 ] 2>/dev/null \
    && ok "LOGIN_3 is free at 14:00 UTC - no overlap with LOGIN_1/LOGIN_2" \
    || fail "LOGIN_3 has $FB_L3_AT14 period(s) at 14:00 UTC (expected 0)"

step "45. FreeBusy - cross-tz: LOGIN_1 queries LOGIN_3 on 22:00-23:00 UTC"
info "LOGIN_3 has event at 22:00 UTC (Asia/Tokyo 07:00+9). Must appear BUSY."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_3\"],
        \"start\": \"2037-06-15T22:00:00Z\",
        \"end\":   \"2037-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy L1->L3 22:00 window" "$CODE" "200"
check_error "POST /freebusy L1->L3 22:00 error_code"
FB_L3_AT22=$(body | jq -r --arg uid "$LOGIN_3" '.data.attendees[$uid].periods | length')
[ "$FB_L3_AT22" -ge 1 ] 2>/dev/null \
    && ok "LOGIN_3 is busy at 22:00 UTC (cross-tz confirmed)" \
    || fail "LOGIN_3 has $FB_L3_AT22 period(s) at 22:00 UTC (expected >= 1)"

step "46. FreeBusy - self-query: LOGIN_2 queries own free/busy"
info "A user querying their own UID must see their own events. Verifies the server-side ownership check does not block self-access."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_2" \
    -d "{
        \"target_uids\": [\"$LOGIN_2\"],
        \"start\": \"2037-06-15T00:00:00Z\",
        \"end\":   \"2037-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy self (LOGIN_2)" "$CODE" "200"
check_error "POST /freebusy self error_code"
FB_SELF=$(body | jq -r --arg uid "$LOGIN_2" '.data.attendees[$uid].periods | length')
[ "$FB_SELF" -ge 1 ] 2>/dev/null \
    && ok "self freebusy returned >= 1 period" \
    || fail "self freebusy returned $FB_SELF periods (expected >= 1)"

step "47. FreeBusy - error: date range > 90 days -> S000614"
info "Queries spanning more than 90 days must be rejected with HTTP 400 + S000614 to prevent expensive server-side scans."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2037-01-01T00:00:00Z\",
        \"end\":   \"2037-12-31T23:59:59Z\"
    }")
check_code "POST /freebusy range too large" "$CODE" "400"
ERR=$(extract '.error_code')
[ "$ERR" = "S000614" ] \
    && ok "range too large -> S000614" \
    || fail "range too large -> $ERR (expected S000614)"

step "48. FreeBusy - show_as tentative -> type tentative"
info "LOGIN_1 creates a TENTATIVE event on 2037-06-16 10:00-11:00 UTC."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Tentative (L1)",
        "date_start": "2037-06-16T10:00:00Z",
        "date_end":   "2037-06-16T11:00:00Z",
        "show_as": "tentative"
    }')
check_code "POST /events FB Tentative L1" "$CODE" "201"
FB_L1_TENTATIVE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2037-06-16T10:00:00Z\",
        \"end\":   \"2037-06-16T11:00:00Z\"
    }")
check_code  "POST /freebusy tentative window" "$CODE" "200"
FB_TENT_TYPE=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods[0].type')
[ "$FB_TENT_TYPE" = "tentative" ] \
    && ok "tentative event -> type=tentative in freebusy" \
    || fail "tentative event -> type=$FB_TENT_TYPE (expected tentative)"

step "49. FreeBusy - show_as free -> excluded"
info "LOGIN_1 creates a FREE event on 2037-06-16 12:00-13:00 UTC. Must not appear in freebusy."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Free (L1)",
        "date_start": "2037-06-16T12:00:00Z",
        "date_end":   "2037-06-16T13:00:00Z",
        "show_as": "free"
    }')
check_code "POST /events FB Free L1" "$CODE" "201"
FB_L1_FREE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2037-06-16T12:00:00Z\",
        \"end\":   \"2037-06-16T13:00:00Z\"
    }")
check_code  "POST /freebusy free window" "$CODE" "200"
FB_FREE_COUNT=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
[ "$FB_FREE_COUNT" -eq 0 ] 2>/dev/null \
    && ok "show_as=free event excluded from freebusy" \
    || fail "show_as=free returned $FB_FREE_COUNT period(s) (expected 0)"

step "50. FreeBusy - status cancelled -> excluded"
info "LOGIN_1 creates a CANCELLED event on 2037-06-16 14:00-15:00 UTC. Must not appear."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Cancelled (L1)",
        "date_start": "2037-06-16T14:00:00Z",
        "date_end":   "2037-06-16T15:00:00Z",
        "show_as": "busy",
        "status": "cancelled"
    }')
check_code "POST /events FB Cancelled L1" "$CODE" "201"
FB_L1_CANCELLED=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2037-06-16T14:00:00Z\",
        \"end\":   \"2037-06-16T15:00:00Z\"
    }")
check_code  "POST /freebusy cancelled window" "$CODE" "200"
FB_CANC_COUNT=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
[ "$FB_CANC_COUNT" -eq 0 ] 2>/dev/null \
    && ok "status=cancelled event excluded from freebusy" \
    || fail "status=cancelled returned $FB_CANC_COUNT period(s) (expected 0)"

step "51. FreeBusy - title: public event exposes title, private event hides it"
info "PUBLIC event -> title in response. PRIVATE event -> no title key."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Public Title Test",
        "date_start": "2037-06-16T08:00:00Z",
        "date_end":   "2037-06-16T09:00:00Z",
        "show_as": "busy",
        "visibility": "public"
    }')
check_code "POST /events FB Public Title L1" "$CODE" "201"
FB_L1_PUBLIC_TITLE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Private Title Test",
        "date_start": "2037-06-16T09:00:00Z",
        "date_end":   "2037-06-16T10:00:00Z",
        "show_as": "busy",
        "visibility": "private"
    }')
check_code "POST /events FB Private Title L1" "$CODE" "201"
FB_L1_PRIVATE_TITLE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2037-06-16T08:00:00Z\",
        \"end\":   \"2037-06-16T09:00:00Z\"
    }")
check_code  "POST /freebusy public title window" "$CODE" "200"
FB_PUB_TITLE=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods[0].title // empty')
[ "$FB_PUB_TITLE" = "Public Title Test" ] \
    && ok "PUBLIC event title exposed in freebusy" \
    || fail "PUBLIC event title = '$FB_PUB_TITLE' (expected 'Public Title Test')"

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2037-06-16T09:00:00Z\",
        \"end\":   \"2037-06-16T10:00:00Z\"
    }")
check_code  "POST /freebusy private title window" "$CODE" "200"
FB_PRIV_HAS_TITLE=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods[0] | has("title")')
[ "$FB_PRIV_HAS_TITLE" = "false" ] \
    && ok "PRIVATE event title hidden in freebusy" \
    || fail "PRIVATE event title key present in freebusy (expected absent)"

# -- 16. INVITATION FLOW -------------------------------------------------------

step "47. Invitation - LOGIN_1 creates event with LOGIN_2 as attendee"
info "Creates an event where LOGIN_2 is invited. The server must immediately propagate a copy to LOGIN_2's default calendar."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Invite Meeting\",
        \"date_start\": \"2037-07-01T14:00:00Z\",
        \"date_end\":   \"2037-07-01T15:00:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"attendees\": [
            {\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"},
            {\"email\": \"$LOGIN_1\", \"name\": \"User One\", \"status\": \"accepted\"}
        ]
    }")
check_code  "POST /events invite" "$CODE" "201"
check_error "POST /events invite error_code"
check_field ".data.title" "Invite Meeting"
INVITE_KEY_L1=$(extract '.data.key')
INVITE_UID=$(extract '.data.uid')
info "Organizer event key (LOGIN_1): $INVITE_KEY_L1  uid: $INVITE_UID"

step "48. Invitation - LOGIN_2 sees the propagated copy in their /events"
info "Without any iMIP mail exchange, LOGIN_2's default calendar should already hold a copy of the event."

CODE=$(req "$BASE/events?start_date_time=2037-07-01T00:00:00Z&end_date_time=2037-07-01T23:59:59Z" -H "$H_AUTH_2")
check_code  "GET /events (LOGIN_2) for invite date" "$CODE" "200"
INVITE_COUNT_L2=$(body | jq --arg uid "$INVITE_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$INVITE_COUNT_L2" -ge 1 ] \
    && ok "LOGIN_2 sees the propagated copy (count=$INVITE_COUNT_L2)" \
    || fail "LOGIN_2 does NOT see the event (count=$INVITE_COUNT_L2)"

INVITE_KEY_L2=$(body | jq -r --arg uid "$INVITE_UID" '[.data.events[] | select(.uid == $uid)][0].key // empty')
info "Attendee event key (LOGIN_2): $INVITE_KEY_L2"

step "49. Invitation - verify attendee status is needs-action on LOGIN_2's copy"
info "Before any response, LOGIN_2's own attendee record should be needs-action."

CODE=$(req "$BASE/events/$INVITE_KEY_L2" -H "$H_AUTH_2")
check_code "GET /events/$INVITE_KEY_L2 (LOGIN_2)" "$CODE" "200"
L2_STATUS=$(body | jq -r --arg email "$LOGIN_2" '.data.attendees[] | select(.email == $email) | .status // empty')
[ "$L2_STATUS" = "needs-action" ] \
    && ok "LOGIN_2 attendee status = needs-action" \
    || fail "LOGIN_2 attendee status = '$L2_STATUS' (expected needs-action)"

step "50. Invitation - LOGIN_2 accepts"
info "POST /events/{key}/attendance with status=accepted. LOGIN_1's organizer copy must reflect ACCEPTED."

CODE=$(req -X POST "$BASE/events/$INVITE_KEY_L2/attendance" \
    -H "$H_JSON" -H "$H_AUTH_2" \
    -d '{"status": "accepted", "sequence": 0}')
check_code  "POST /events/$INVITE_KEY_L2/attendance accepted" "$CODE" "200"
check_error "POST attendance accepted error_code"
L2_NEW_STATUS=$(body | jq -r --arg email "$LOGIN_2" '.data.attendees[] | select(.email == $email) | .status // empty')
[ "$L2_NEW_STATUS" = "accepted" ] \
    && ok "response shows LOGIN_2 status = accepted" \
    || fail "response status = '$L2_NEW_STATUS' (expected accepted)"

step "51. Invitation - LOGIN_1 sees ACCEPTED on the organizer copy"
info "After LOGIN_2 accepts, propagate_partstat_to_copies must have updated the organizer's copy."

CODE=$(req "$BASE/events/$INVITE_KEY_L1" -H "$H_AUTH")
check_code "GET /events/$INVITE_KEY_L1 (LOGIN_1)" "$CODE" "200"
L2_STATUS_ON_L1=$(body | jq -r --arg email "$LOGIN_2" '.data.attendees[] | select(.email == $email) | .status // empty')
[ "$L2_STATUS_ON_L1" = "accepted" ] \
    && ok "LOGIN_1 organizer copy shows LOGIN_2 = accepted" \
    || fail "LOGIN_1 organizer copy shows LOGIN_2 = '$L2_STATUS_ON_L1' (expected accepted)"

step "51 (cont.) - Attendee sets a personal reminder on their own copy"
info "An attendee is not the organizer but still owns their VALARM (RFC 6638): LOGIN_2 must be able to
  add a reminder on their copy, and it must NOT propagate to the organizer's copy."

CODE=$(req -X PATCH "$BASE/events/$INVITE_KEY_L2" -H "$H_JSON" -H "$H_AUTH_2" \
    -d '{"reminders": [{"method": "email", "minutes_before": 30}]}')
check_code  "PATCH attendee personal reminder" "$CODE" "200"
check_error "PATCH attendee personal reminder error_code"

CODE=$(req "$BASE/events/$INVITE_KEY_L2" -H "$H_AUTH_2")
REM_COUNT_L2=$(body | jq -r '.data.reminders | length')
[ "$REM_COUNT_L2" = "1" ] \
    && ok "LOGIN_2 copy now carries the personal reminder" \
    || fail "LOGIN_2 reminder count=$REM_COUNT_L2 (expected 1)"

CODE=$(req "$BASE/events/$INVITE_KEY_L1" -H "$H_AUTH")
REM_COUNT_L1=$(body | jq -r '.data.reminders | length')
[ "$REM_COUNT_L1" = "0" ] \
    && ok "organizer copy unaffected (personal reminders do not propagate)" \
    || fail "organizer copy reminder count=$REM_COUNT_L1 (expected 0)"

step "51a. iMIP - LOGIN_2 receives the invitation email"
info "Creating an event with attendees sends an iMIP REQUEST (RFC 6047) to each attendee. We create an
  event with a unique title, then poll LOGIN_2's INBOX through the Mail Account API to confirm delivery."

IMIP_NONCE=$(date +%s)
IMIP_TITLE="iMIP Invite $IMIP_NONCE"
IMIP_SUBJECT="Invitation: $IMIP_TITLE"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"$IMIP_TITLE\",
        \"date_start\": \"2037-07-02T09:00:00Z\",
        \"date_end\":   \"2037-07-02T10:00:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"attendees\": [
            {\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"}
        ]
    }")
check_code  "POST /events iMIP invite" "$CODE" "201"
IMIP_EVT_KEY=$(extract '.data.key')

info "Polling LOGIN_2 INBOX for subject: $IMIP_SUBJECT"
IMIP_MAIL_UID=""
for _ in $(seq 1 15); do
    CODE=$(req "$BASE/mailboxes/0/folders/INBOX/mails?sort_by=date&sort_order=desc&fields=contents&fields_action=exclude" \
        -H "$H_AUTH_2")
    if [ "$CODE" = "200" ]; then
        IMIP_MAIL_UID=$(body | jq -r --arg subj "$IMIP_SUBJECT" '[.data[] | select(.subject == $subj)][0].uid // empty')
        [ -n "$IMIP_MAIL_UID" ] && break
    fi
    sleep 1
done

if [ -n "$IMIP_MAIL_UID" ]; then
    ok "LOGIN_2 received the iMIP invitation (mail uid=$IMIP_MAIL_UID)"

    CODE=$(req "$BASE/mailboxes/0/folders/INBOX/mails/$IMIP_MAIL_UID/raw" -H "$H_AUTH_2")
    check_code "GET raw iMIP mail" "$CODE" "200"
    IMIP_RAW=$(body | jq -r '.data.raw // empty')
    echo "$IMIP_RAW" | grep -q "BEGIN:VCALENDAR" \
        && ok "iMIP mail carries an iCalendar payload (BEGIN:VCALENDAR)" \
        || fail "iMIP mail has no VCALENDAR payload"
    echo "$IMIP_RAW" | grep -qi "METHOD:REQUEST" \
        && ok "iMIP mail iTIP method is REQUEST" \
        || fail "iMIP mail is missing METHOD:REQUEST"
else
    fail "LOGIN_2 did NOT receive the iMIP invitation (subject '$IMIP_SUBJECT' not found after polling)"
fi

step "51a (cont.) - iMIP REQUEST re-sent to LOGIN_2 on PATCH"
info "Modifying an organizer's event with attendees must re-send an iMIP REQUEST. We PATCH the title
  and poll LOGIN_2's INBOX for an invitation carrying the new subject."

IMIP_TITLE_UPD="iMIP Update $IMIP_NONCE"
IMIP_SUBJECT_UPD="Invitation: $IMIP_TITLE_UPD"

CODE=$(req -X PATCH "$BASE/events/$IMIP_EVT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{\"title\": \"$IMIP_TITLE_UPD\"}")
check_code "PATCH /events iMIP invite (title)" "$CODE" "200"

info "Polling LOGIN_2 INBOX for subject: $IMIP_SUBJECT_UPD"
IMIP_UPD_UID=""
for _ in $(seq 1 15); do
    CODE=$(req "$BASE/mailboxes/0/folders/INBOX/mails?sort_by=date&sort_order=desc&fields=contents&fields_action=exclude" \
        -H "$H_AUTH_2")
    if [ "$CODE" = "200" ]; then
        IMIP_UPD_UID=$(body | jq -r --arg subj "$IMIP_SUBJECT_UPD" '[.data[] | select(.subject == $subj)][0].uid // empty')
        [ -n "$IMIP_UPD_UID" ] && break
    fi
    sleep 1
done

[ -n "$IMIP_UPD_UID" ] \
    && ok "LOGIN_2 received the updated iMIP REQUEST (mail uid=$IMIP_UPD_UID)" \
    || fail "LOGIN_2 did NOT receive the updated iMIP REQUEST (subject '$IMIP_SUBJECT_UPD' not found)"

step "51a (cont.) - iMIP CANCEL sent to LOGIN_2 on delete"
info "When the organizer deletes an event with attendees, an iMIP CANCEL (RFC 6047) must reach each
  attendee. Deleting the event here also doubles as cleanup for this section."

IMIP_SUBJECT_CANCEL="Cancelled: $IMIP_TITLE_UPD"

CODE=$(req -X DELETE "$BASE/events/$IMIP_EVT_KEY" -H "$H_AUTH")
check_code "DELETE /events iMIP invite" "$CODE" "200"

info "Polling LOGIN_2 INBOX for subject: $IMIP_SUBJECT_CANCEL"
IMIP_CANCEL_UID=""
for _ in $(seq 1 15); do
    CODE=$(req "$BASE/mailboxes/0/folders/INBOX/mails?sort_by=date&sort_order=desc&fields=contents&fields_action=exclude" \
        -H "$H_AUTH_2")
    if [ "$CODE" = "200" ]; then
        IMIP_CANCEL_UID=$(body | jq -r --arg subj "$IMIP_SUBJECT_CANCEL" '[.data[] | select(.subject == $subj)][0].uid // empty')
        [ -n "$IMIP_CANCEL_UID" ] && break
    fi
    sleep 1
done

if [ -n "$IMIP_CANCEL_UID" ]; then
    ok "LOGIN_2 received the iMIP cancellation (mail uid=$IMIP_CANCEL_UID)"

    CODE=$(req "$BASE/mailboxes/0/folders/INBOX/mails/$IMIP_CANCEL_UID/raw" -H "$H_AUTH_2")
    check_code "GET raw iMIP cancel mail" "$CODE" "200"
    IMIP_CANCEL_RAW=$(body | jq -r '.data.raw // empty')
    echo "$IMIP_CANCEL_RAW" | grep -qi "METHOD:CANCEL" \
        && ok "iMIP cancel mail iTIP method is CANCEL" \
        || fail "iMIP cancel mail is missing METHOD:CANCEL"
else
    fail "LOGIN_2 did NOT receive the iMIP cancellation (subject '$IMIP_SUBJECT_CANCEL' not found)"
fi

step "51a (cont.) - iMIP REPLY sent to organizer when LOGIN_2 responds"
info "When an attendee sets their attendance, an iMIP REPLY (RFC 6047) must reach the organizer. LOGIN_1
  invites LOGIN_2, LOGIN_2 accepts, and we poll LOGIN_1's INBOX for the reply. Opening that reply through
  the Mail Account detail endpoint also exercises the inbound iMIP hook (it must not break mail display)."

REPLY_NONCE=$(date +%s)
REPLY_TITLE="iMIP Reply $REPLY_NONCE"
REPLY_SUBJECT="Re: $REPLY_TITLE"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"$REPLY_TITLE\",
        \"date_start\": \"2037-07-03T09:00:00Z\",
        \"date_end\":   \"2037-07-03T10:00:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"attendees\": [ {\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"} ]
    }")
check_code "POST /events iMIP reply-source" "$CODE" "201"
REPLY_UID=$(extract '.data.uid')
REPLY_EVT_KEY=$(extract '.data.key')

CODE=$(req "$BASE/events?start_date_time=2037-07-03T00:00:00Z&end_date_time=2037-07-03T23:59:59Z" -H "$H_AUTH_2")
REPLY_KEY_L2=$(body | jq -r --arg uid "$REPLY_UID" '[.data.events[] | select(.uid == $uid)][0].key // empty')
[ -n "$REPLY_KEY_L2" ] \
    && ok "LOGIN_2 sees the invitation copy (key=$REPLY_KEY_L2)" \
    || fail "LOGIN_2 does not see the invitation copy for uid=$REPLY_UID"

CODE=$(req -X POST "$BASE/events/$REPLY_KEY_L2/attendance" -H "$H_JSON" -H "$H_AUTH_2" -d '{"status": "accepted", "sequence": 0}')
check_code "POST /events/$REPLY_KEY_L2/attendance accepted" "$CODE" "200"

info "Polling LOGIN_1 INBOX for subject: $REPLY_SUBJECT"
REPLY_MAIL_UID=""
for _ in $(seq 1 15); do
    CODE=$(req "$BASE/mailboxes/0/folders/INBOX/mails?sort_by=date&sort_order=desc&fields=contents&fields_action=exclude" \
        -H "$H_AUTH")
    if [ "$CODE" = "200" ]; then
        REPLY_MAIL_UID=$(body | jq -r --arg subj "$REPLY_SUBJECT" '[.data[] | select(.subject == $subj)][0].uid // empty')
        [ -n "$REPLY_MAIL_UID" ] && break
    fi
    sleep 1
done

if [ -n "$REPLY_MAIL_UID" ]; then
    ok "Organizer LOGIN_1 received the iMIP reply (mail uid=$REPLY_MAIL_UID)"

    CODE=$(req "$BASE/mailboxes/0/folders/INBOX/mails/$REPLY_MAIL_UID/raw" -H "$H_AUTH")
    REPLY_RAW=$(body | jq -r '.data.raw // empty')
    echo "$REPLY_RAW" | grep -qi "METHOD:REPLY" \
        && ok "iMIP reply mail iTIP method is REPLY" \
        || fail "iMIP reply mail is missing METHOD:REPLY"

    # Inbound hook - real assertion. Same-server propagation already set the organizer copy to
    # accepted when LOGIN_2 responded, so we move it away first, then inject a FRESH reply through
    # the MTA and open it: applying it proves the inbound hook. Re-opening the original mail would
    # not work anymore - its DTSTAMP predates the decline, so reply ordering (RFC 5546 2.1.5)
    # correctly refuses it as delivered out of order.
    CODE=$(req -X POST "$BASE/events/$REPLY_KEY_L2/attendance" -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"status": "declined", "sequence": 0}')
    check_code "LOGIN_2 moves away from accepted (no SEQUENCE change)" "$CODE" "200"

    CODE=$(req "$BASE/events/$REPLY_EVT_KEY" -H "$H_AUTH")
    PRE_STATUS=$(body | jq -r --arg e "$LOGIN_2" '.data.attendees[] | select(.email == $e) | .status // empty')
    [ "$PRE_STATUS" = "declined" ] \
        && ok "organizer copy moved to declined before the inbound hook" \
        || fail "could not move the organizer copy (status='$PRE_STATUS')"

    HOOK_SUBJ="Inbound hook $REPLY_NONCE"
    # Fixed far-future stamp: guaranteed newer than the decline's server-side timestamp whatever
    # the client/server clock offset, and deterministic across runs.
    HOOK_DTSTAMP="20380101T120000Z"
    send_imip_mail "$LOGIN_2" "$LOGIN_1" "$HOOK_SUBJ" \
        "$(build_reply_ics "$REPLY_UID" 0 "20370703T090000Z" \
            "ATTENDEE;PARTSTAT=ACCEPTED:mailto:$LOGIN_2" "$HOOK_DTSTAMP")"
    if open_mail_by_subject "$H_AUTH" "$HOOK_SUBJ" >/dev/null; then
        CODE=$(req "$BASE/events/$REPLY_EVT_KEY" -H "$H_AUTH")
        POST_STATUS=$(body | jq -r --arg e "$LOGIN_2" '.data.attendees[] | select(.email == $e) | .status // empty')
        [ "$POST_STATUS" = "accepted" ] \
            && ok "opening the reply applied the response (LOGIN_2 -> accepted via inbound iMIP)" \
            || fail "inbound iMIP did not update the event (status='$POST_STATUS', expected accepted)"
    else
        fail "crafted inbound-hook reply never reached the organizer INBOX"
    fi
else
    fail "Organizer LOGIN_1 did NOT receive the iMIP reply (subject '$REPLY_SUBJECT' not found)"
fi

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/events/$REPLY_EVT_KEY" -H "$H_AUTH")
    info "Cleanup reply-source event (key=$REPLY_EVT_KEY): HTTP $CODE"
fi

# -- 17b. SINGLE-OCCURRENCE ATTENDANCE ----------------------------------------

step "51b. Invitation - LOGIN_1 creates recurring event with LOGIN_2 as attendee"
info "Creates a recurring event where LOGIN_2 is invited. Then LOGIN_2 declines a single occurrence."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Weekly Sync\",
        \"date_start\": \"2037-07-06T14:00:00Z\",
        \"date_end\":   \"2037-07-06T15:00:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"recurrence_rule\": {\"frequency\": \"weekly\", \"count\": 4, \"interval\": 1},
        \"attendees\": [
            {\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"},
            {\"email\": \"$LOGIN_1\", \"name\": \"User One\", \"status\": \"accepted\"}
        ]
    }")
check_code  "POST /events recurring invite" "$CODE" "201"
check_error "POST /events recurring invite error_code"
REC_INVITE_KEY_L1=$(extract '.data.key')
REC_INVITE_UID=$(extract '.data.uid')
info "Recurring invite organizer key (LOGIN_1): $REC_INVITE_KEY_L1  uid: $REC_INVITE_UID"

# Fetch LOGIN_2's copy
CODE=$(req "$BASE/events?start_date_time=2037-07-06T00:00:00Z&end_date_time=2037-07-06T23:59:59Z" -H "$H_AUTH_2")
check_code "GET /events (LOGIN_2) for recurring invite" "$CODE" "200"
REC_INVITE_KEY_L2=$(body | jq -r --arg uid "$REC_INVITE_UID" '[.data.events[] | select(.uid == $uid)][0].key // empty')
info "Recurring invite attendee key (LOGIN_2): $REC_INVITE_KEY_L2"

step "51c. Invitation - LOGIN_2 declines single occurrence of recurring event"
info "POST /events/{key}/attendance with status=declined and recurrence_id targeting 2037-07-13."

CODE=$(req -X POST "$BASE/events/$REC_INVITE_KEY_L2/attendance" \
    -H "$H_JSON" -H "$H_AUTH_2" \
    -d '{"status": "declined", "sequence": 0, "recurrence_id": "2037-07-13T14:00:00Z"}')
check_code  "POST /events/$REC_INVITE_KEY_L2/attendance declined single occ" "$CODE" "200"
check_error "POST attendance declined single occ error_code"
OCC_RECID=$(body | jq -r '.data.recurrence_id // empty' | sed 's/\.000Z$/Z/')
[ "$OCC_RECID" = "2037-07-13T14:00:00Z" ] \
    && ok "response has recurrence_id = 2037-07-13T14:00:00Z" \
    || fail "response recurrence_id = '$OCC_RECID' (expected 2037-07-13T14:00:00Z)"
OCC_ATT_KEY=$(body | jq -r '.data.key // empty')
OCC_L2_STATUS=$(body | jq -r --arg email "$LOGIN_2" '.data.attendees[] | select(.email == $email) | .status // empty')
[ "$OCC_L2_STATUS" = "declined" ] \
    && ok "occurrence attendee status = declined" \
    || fail "occurrence attendee status = '$OCC_L2_STATUS' (expected declined)"
info "Occurrence key: $OCC_ATT_KEY"

# -- 18. RECURRENCE SCOPE (THISANDFUTURE + SINGLE OCCURRENCE) -----------------

step "52. Recurrence scope - edit single occurrence (PATCH with recurrence_id, no range)"
info "PATCH the weekly Cardio Session event with recurrence_id=2037-06-08T07:00:00Z (a Monday).
  Expected: a detached occurrence row is created; recurrence_id is set on the response."

# Capture WEEKLY_UID for later assertion
CODE=$(req "$BASE/events/$WEEKLY_KEY" -H "$H_AUTH")
check_code "GET /events/$WEEKLY_KEY to capture uid" "$CODE" "200"
WEEKLY_UID=$(extract '.data.uid')
info "Weekly event uid: $WEEKLY_UID"

CODE=$(req -X PATCH "$BASE/events/$WEEKLY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Cardio Session (modified)",
        "recurrence_id": "2037-06-08T07:00:00Z"
    }')
check_code  "PATCH /events edit single occurrence" "$CODE" "200"
check_error "PATCH /events edit single occurrence error_code"
RECID=$(extract '.data.recurrence_id' | sed 's/\.000Z$/Z/')
[ "$RECID" = "2037-06-08T07:00:00Z" ] \
    && ok "recurrence_id set to 2037-06-08T07:00:00Z" \
    || fail "recurrence_id '$RECID' != '2037-06-08T07:00:00Z'"
OCCURRENCE_EDIT_KEY=$(extract '.data.key')
info "Detached occurrence key: $OCCURRENCE_EDIT_KEY"

step "53. Recurrence scope - THISANDFUTURE split with updates (PATCH + recurrence_range)"
info "PATCH weekly Cardio Session with recurrence_id=2037-06-15T07:00:00Z and
  recurrence_range=THISANDFUTURE. Expected:
  - Original series is truncated at 2037-06-14T23:59:59Z
  - A new master event is created from 2037-06-15 with the given title
  - Response has no recurrence_id (it is a new master, not a detached occurrence)"

CODE=$(req -X PATCH "$BASE/events/$WEEKLY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Cardio Session - New Series",
        "recurrence_id": "2037-06-15T07:00:00Z",
        "recurrence_range": "THISANDFUTURE"
    }')
check_code  "PATCH /events THISANDFUTURE split" "$CODE" "200"
check_error "PATCH /events THISANDFUTURE split error_code"
SPLIT_KEY=$(extract '.data.key')
SPLIT_UID=$(extract '.data.uid')
SPLIT_RECID=$(extract '.data.recurrence_id // empty')
[ -z "$SPLIT_RECID" ] \
    && ok "new master has no recurrence_id (it is a master, not a detached occurrence)" \
    || fail "new master should have no recurrence_id, got '$SPLIT_RECID'"
SPLIT_TITLE=$(extract '.data.title')
[ "$SPLIT_TITLE" = "Cardio Session - New Series" ] \
    && ok "new master title = 'Cardio Session - New Series'" \
    || fail "new master title '$SPLIT_TITLE' != expected"
info "Split master key: $SPLIT_KEY  uid: $SPLIT_UID"

step "54. Recurrence scope - verify original series is truncated after split"
info "GET the original weekly event and verify its recurrence_rule.until is set to a date
  before 2037-06-15 (the split point). The series should no longer expand past that point."

CODE=$(req "$BASE/events/$WEEKLY_KEY" -H "$H_AUTH")
check_code "GET /events/$WEEKLY_KEY (truncated original)" "$CODE" "200"
UNTIL=$(extract '.data.recurrence_rule.until // empty')
[ -n "$UNTIL" ] \
    && ok "original series has until set after split ($UNTIL)" \
    || fail "original series until is empty - series not truncated"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-15T00:00:00Z&end_date_time=2037-06-15T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events on split point date" "$CODE" "200"
CARDIO_ORIGINAL=$(body | jq --arg uid "$WEEKLY_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$CARDIO_ORIGINAL" -eq 0 ] 2>/dev/null \
    && ok "original series absent from 2037-06-15 onwards (truncated)" \
    || fail "original series still appears on 2037-06-15 (count=$CARDIO_ORIGINAL)"
CARDIO_SPLIT=$(body | jq --arg uid "$SPLIT_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$CARDIO_SPLIT" -ge 1 ] 2>/dev/null \
    && ok "new split series appears on 2037-06-15 (count=$CARDIO_SPLIT)" \
    || fail "new split series absent from 2037-06-15 (count=$CARDIO_SPLIT)"

step "55. Recurrence scope - THISANDFUTURE truncate only (no updates = delete this and following)"
info "PATCH a recurring event with recurrence_id + recurrence_range=THISANDFUTURE but no
  content updates (empty updates dict). Expected: the series is truncated at that point
  but no new master is created. Response returns the (now-truncated) original master."

CODE=$(req -X PATCH "$BASE/events/$SPLIT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "recurrence_id": "2037-06-22T07:00:00Z",
        "recurrence_range": "THISANDFUTURE"
    }')
check_code  "PATCH /events THISANDFUTURE truncate-only" "$CODE" "200"
check_error "PATCH /events THISANDFUTURE truncate-only error_code"
TRUNC_UNTIL=$(extract '.data.recurrence_rule.until // empty')
[ -n "$TRUNC_UNTIL" ] \
    && ok "truncated series has until set ($TRUNC_UNTIL)" \
    || fail "series until is empty after truncate-only"
TRUNC_UID=$(extract '.data.uid')
[ "$TRUNC_UID" = "$SPLIT_UID" ] \
    && ok "response is still the same master (no new event created)" \
    || fail "unexpected uid change: got '$TRUNC_UID', expected '$SPLIT_UID'"

step "56. Recurrence scope - THISANDFUTURE on COUNT-based series converts to UNTIL"
info "PATCH the monthly COUNT=6 event with THISANDFUTURE at 2037-09-01 (4th occurrence).
  Expected: new series has UNTIL instead of COUNT, and COUNT is null."

CODE=$(req "$BASE/events/$MONTHLY_KEY" -H "$H_AUTH")
check_code "GET /events/$MONTHLY_KEY to capture uid" "$CODE" "200"
MONTHLY_UID=$(extract '.data.uid')

CODE=$(req -X PATCH "$BASE/events/$MONTHLY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Monthly Review - New Series",
        "recurrence_id": "2037-09-01T10:00:00Z",
        "recurrence_range": "THISANDFUTURE"
    }')
check_code "PATCH /events THISANDFUTURE on COUNT series" "$CODE" "200"
check_error "PATCH /events THISANDFUTURE on COUNT series error_code"
SPLIT_MONTHLY_KEY=$(extract '.data.key')
SPLIT_MONTHLY_COUNT=$(extract '.data.recurrence_rule.count // empty')
SPLIT_MONTHLY_UNTIL=$(extract '.data.recurrence_rule.until // empty')
[ -z "$SPLIT_MONTHLY_COUNT" ] \
    && ok "new series has no COUNT (converted to UNTIL)" \
    || fail "new series still has COUNT=$SPLIT_MONTHLY_COUNT"
[ -n "$SPLIT_MONTHLY_UNTIL" ] \
    && ok "new series has UNTIL set ($SPLIT_MONTHLY_UNTIL)" \
    || fail "new series UNTIL is empty - COUNT was not converted"
info "Split monthly key: $SPLIT_MONTHLY_KEY  until: $SPLIT_MONTHLY_UNTIL"

step "57. Recurrence scope - edit occurrence then verify via GET expansion"
info "After step 52 created a detached occurrence for the weekly event on 2037-06-08,
  GET over that date range must show the modified title, not the original."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-08T00:00:00Z&end_date_time=2037-06-08T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events June 8 (with occurrence edit)" "$CODE" "200"
OVERRIDE_TITLE=$(body | jq -r '[.data.events[] | select(.title == "Cardio Session (modified)")] | length')
[ "$OVERRIDE_TITLE" -ge 1 ] 2>/dev/null \
    && ok "modified occurrence appears in expansion (count=$OVERRIDE_TITLE)" \
    || fail "modified occurrence not found in expansion (count=$OVERRIDE_TITLE)"
ORIGINAL_SLOT=$(body | jq -r '[.data.events[] | select(.title == "Cardio Session" and .recurrence_id == null)] | length')
[ "$ORIGINAL_SLOT" -eq 0 ] 2>/dev/null \
    && ok "original slot replaced by override" \
    || fail "original slot still present alongside override (count=$ORIGINAL_SLOT)"

step "58. Recurrence scope - split series then verify new series expands"
info "After step 53 created a new series 'Cardio Session - New Series' starting 2037-06-15,
  GET over 2037-06-15 to 2037-06-22 must show occurrences from the new series."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-15T00:00:00Z&end_date_time=2037-06-22T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events June 15-22 (split series expansion)" "$CODE" "200"
SPLIT_OCCURRENCES=$(body | jq --arg uid "$SPLIT_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$SPLIT_OCCURRENCES" -ge 1 ] 2>/dev/null \
    && ok "new split series expands correctly ($SPLIT_OCCURRENCES occurrences)" \
    || fail "new split series has 0 occurrences in June 15-22"

step "59. Error - THISANDFUTURE on non-recurring event"
info "PATCH a non-recurring event with recurrence_id + THISANDFUTURE must fail."

CODE=$(req -X PATCH "$BASE/events/$EVT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Should fail",
        "recurrence_id": "2037-06-10T09:00:00Z",
        "recurrence_range": "THISANDFUTURE"
    }')
[ "$CODE" != "200" ] \
    && ok "THISANDFUTURE on non-recurring event rejected (HTTP $CODE)" \
    || fail "THISANDFUTURE on non-recurring event should not succeed (HTTP $CODE)"

step "60. DELETE master recurring event removes all occurrences"
info "Create a temporary daily recurring event, then DELETE the master.
  A subsequent GET must return 0 occurrences for that uid."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Temp Recurring",
        "date_start": "2037-06-20T08:00:00Z",
        "date_end":   "2037-06-20T09:00:00Z",
        "recurrence_rule": {"frequency": "daily", "count": 3, "interval": 1}
    }')
check_code "POST /events temp recurring" "$CODE" "201"
TEMP_REC_KEY=$(extract '.data.key')
TEMP_REC_UID=$(extract '.data.uid')

CODE=$(req -X DELETE "$BASE/events/$TEMP_REC_KEY" -H "$H_AUTH")
check_code "DELETE /events/$TEMP_REC_KEY (master)" "$CODE" "200"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-20T00:00:00Z&end_date_time=2037-06-22T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events after master delete" "$CODE" "200"
REMAINING=$(body | jq --arg uid "$TEMP_REC_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$REMAINING" -eq 0 ] 2>/dev/null \
    && ok "no occurrences remain after master delete" \
    || fail "occurrences still present after master delete (count=$REMAINING)"

step "61. EXDATE on slot without detached override"
info "PATCH the daily event to add 2037-06-04T09:00:00Z to recurrence_exceptions.
  That slot has no detached override - it is a pure RRULE-generated slot.
  After the EXDATE, that slot must vanish from expansion."

CODE=$(req -X PATCH "$BASE/events/$DAILY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"recurrence_exceptions": ["2037-06-03T09:00:00Z", "2037-06-04T09:00:00Z"]}')
check_code "PATCH /events add EXDATE for June 4" "$CODE" "200"
EXDATES=$(extract '.data.recurrence_exceptions | length')
[ "$EXDATES" -ge 2 ] 2>/dev/null \
    && ok "recurrence_exceptions has $EXDATES entries (includes June 3 + June 4)" \
    || fail "recurrence_exceptions count $EXDATES < 2"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2037-06-04T00:00:00Z&end_date_time=2037-06-04T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events June 4 after EXDATE" "$CODE" "200"
STANDUP_COUNT=$(body | jq --arg uid "$DAILY_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$STANDUP_COUNT" -eq 0 ] 2>/dev/null \
    && ok "Daily Standup absent from June 4 after EXDATE" \
    || fail "Daily Standup still present on June 4 (count=$STANDUP_COUNT)"

step "62. All-events update shifts detached occurrences"
info "Create a daily recurring event, override one occurrence (change color),
  then PATCH the master with new date_start (+2h). The detached occurrence
  must shift its recurrence_id and dates by the same delta."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Shift Test",
        "date_start": "2037-06-20T10:00:00Z",
        "date_end":   "2037-06-20T11:00:00Z",
        "recurrence_rule": {"frequency": "daily", "count": 3, "interval": 1}
    }')
check_code "POST /events shift test" "$CODE" "201"
SHIFT_KEY=$(extract '.data.key')
SHIFT_UID=$(extract '.data.uid')

# Create detached occurrence for June 21 with different color
CODE=$(req -X PATCH "$BASE/events/$SHIFT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"color": "#ff0000", "recurrence_id": "2037-06-21T10:00:00Z"}')
check_code "PATCH /events create detached for shift test" "$CODE" "200"
SHIFT_OCC_KEY=$(extract '.data.key')

# Move master +2h with "all events"
CODE=$(req -X PATCH "$BASE/events/$SHIFT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"date_start": "2037-06-20T12:00:00Z", "date_end": "2037-06-20T13:00:00Z"}')
check_code "PATCH /events shift master +2h" "$CODE" "200"

# Verify the detached occurrence shifted by +2h
CODE=$(req "$BASE/events/$SHIFT_OCC_KEY" -H "$H_AUTH")
check_code "GET shifted detached occurrence" "$CODE" "200"
OCC_RECID=$(extract '.data.recurrence_id' | sed 's/\.000Z$/Z/')
OCC_START=$(extract '.data.date_start' | sed 's/\.000Z$/Z/')
[ "$OCC_RECID" = "2037-06-21T12:00:00Z" ] \
    && ok "detached occurrence recurrence_id shifted to 12:00" \
    || fail "recurrence_id '$OCC_RECID' (expected 2037-06-21T12:00:00Z)"
[ "$OCC_START" = "2037-06-21T12:00:00Z" ] \
    && ok "detached occurrence date_start shifted to 12:00" \
    || fail "date_start '$OCC_START' (expected 2037-06-21T12:00:00Z)"
OCC_COLOR=$(extract '.data.color')
[ "$OCC_COLOR" = "#ff0000" ] \
    && ok "detached occurrence color preserved (#ff0000)" \
    || fail "color '$OCC_COLOR' (expected #ff0000)"

step "63. Detached occurrence edit does not break attendee master"
info "LOGIN_1 creates a weekly recurring event with LOGIN_2 as attendee.
  LOGIN_1 edits one occurrence (color change -> detached occurrence).
  LOGIN_1 moves the detached occurrence. LOGIN_2's master must survive."

# Create recurring event with attendee
CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Propagation Test\",
        \"date_start\": \"2037-06-25T10:00:00Z\",
        \"date_end\":   \"2037-06-25T11:00:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"recurrence_rule\": {\"frequency\": \"weekly\", \"interval\": 1, \"count\": 4},
        \"attendees\": [{\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"}]
    }")
check_code "POST /events propagation test" "$CODE" "201"
PROP_KEY=$(extract '.data.key')
PROP_UID=$(extract '.data.uid')
info "Propagation test key: $PROP_KEY  uid: $PROP_UID"

# Edit single occurrence (change color) -> creates detached occurrence
CODE=$(req -X PATCH "$BASE/events/$PROP_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"color": "#ff0000", "recurrence_id": "2037-07-02T10:00:00Z"}')
check_code "PATCH /events create detached for propagation test" "$CODE" "200"
PROP_OCC_KEY=$(extract '.data.key')

# Move the detached occurrence by +1h
CODE=$(req -X PATCH "$BASE/events/$PROP_OCC_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"date_start": "2037-07-02T11:00:00Z", "date_end": "2037-07-02T12:00:00Z"}')
check_code "PATCH /events move detached occurrence" "$CODE" "200"

# Verify LOGIN_2 still sees the full recurring series (not just the detached occurrence)
CODE=$(req "$BASE/events?start_date_time=2037-06-25T00:00:00Z&end_date_time=2037-07-16T23:59:59Z" -H "$H_AUTH_2")
check_code "GET /events (LOGIN_2) after detached move" "$CODE" "200"
L2_SERIES=$(body | jq --arg uid "$PROP_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$L2_SERIES" -ge 3 ] 2>/dev/null \
    && ok "LOGIN_2 still sees full series ($L2_SERIES occurrences)" \
    || fail "LOGIN_2 only sees $L2_SERIES occurrence(s) (expected >= 3)"

# Verify LOGIN_2's master has recurrence_rule intact
L2_MASTER_RRULE=$(body | jq -r --arg uid "$PROP_UID" '[.data.events[] | select(.uid == $uid and .recurrence_rule != null)][0].recurrence_rule.frequency // empty')
[ "$L2_MASTER_RRULE" = "weekly" ] \
    && ok "LOGIN_2 master recurrence_rule intact (weekly)" \
    || fail "LOGIN_2 master recurrence_rule='$L2_MASTER_RRULE' (expected weekly)"

# -- 17. CONDITIONAL DELETES ---------------------------------------------------

step "64. Error - attendee cannot move (reschedule) the organizer's event"
info "LOGIN_2 tries to move their copy of the invitation from step 47 (new date_start/date_end).
  Rescheduling is organizer-only content (RFC 6638): the attendee must be rejected with 403 / S000618
  and the request must change nothing - personal-only edits are covered by step 51 (cont.)."

# Use the propagated copy key from step 48 (LOGIN_2's copy of the invite)
if [ -n "$INVITE_KEY_L2" ]; then
    CODE=$(req -X PATCH "$BASE/events/$INVITE_KEY_L2" \
        -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"date_start": "2037-07-02T18:00:00Z", "date_end": "2037-07-02T19:00:00Z"}')
    check_code "attendee reschedule rejected" "$CODE" "403"
    ERR_CODE=$(body | jq -r '.error_code // empty')
    [ "$ERR_CODE" = "S000618" ] \
        && ok "error code = S000618 (not organizer)" \
        || fail "error code = '$ERR_CODE' (expected S000618)"

    # The move must not have been persisted on the attendee copy (still on 2037-07-01).
    CODE=$(req "$BASE/events/$INVITE_KEY_L2" -H "$H_AUTH_2")
    NEW_START=$(body | jq -r '.data.date_start // empty')
    case "$NEW_START" in
        2037-07-01*) ok "event not moved (date_start still $NEW_START)" ;;
        *)           fail "attendee moved the event (date_start=$NEW_START)" ;;
    esac
else
    skip "attendee modify test (no INVITE_KEY_L2 from step 48)"
fi

step "65. End-to-end recurring event lifecycle with attendee"
info "Full lifecycle: create recurring event with attendee, detach one occurrence,
  move all events, verify attendee sync at every step, then delete everything."

# 1. Create recurring event MO/TH, 30 occurrences, with LOGIN_2 as attendee
CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Foo\",
        \"date_start\": \"2037-07-06T12:00:00Z\",
        \"date_end\":   \"2037-07-06T13:00:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"recurrence_rule\": {\"frequency\": \"weekly\", \"interval\": 1, \"by_day\": [\"MO\", \"TH\"], \"count\": 30},
        \"attendees\": [{\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"}]
    }")
check_code "E2E: create recurring event" "$CODE" "201"
E2E_KEY=$(extract '.data.key')
E2E_UID=$(extract '.data.uid')
info "E2E key: $E2E_KEY  uid: $E2E_UID"

# 2. Verify LOGIN_2 sees the events
CODE=$(req "$BASE/events?start_date_time=2037-07-06T00:00:00Z&end_date_time=2037-07-20T23:59:59Z" -H "$H_AUTH_2")
check_code "E2E: LOGIN_2 sees events" "$CODE" "200"
L2_E2E_COUNT=$(body | jq --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$L2_E2E_COUNT" -ge 4 ] 2>/dev/null \
    && ok "LOGIN_2 sees $L2_E2E_COUNT occurrences in first 2 weeks" \
    || fail "LOGIN_2 sees $L2_E2E_COUNT occurrences (expected >= 4)"

# 3. Edit second occurrence: change color, title, shift +1h -> creates detached occurrence
# Second occurrence is Thursday July 9 at 12:00
CODE=$(req -X PATCH "$BASE/events/$E2E_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Foo Modified", "color": "#ff0000", "date_start": "2037-07-09T13:00:00Z", "date_end": "2037-07-09T14:00:00Z", "recurrence_id": "2037-07-09T12:00:00Z"}')
check_code "E2E: create detached occurrence" "$CODE" "200"
E2E_OCC_KEY=$(extract '.data.key')
E2E_OCC_TITLE=$(extract '.data.title')
E2E_OCC_COLOR=$(extract '.data.color')
E2E_OCC_START=$(extract '.data.date_start' | sed 's/\.000Z$/Z/')
[ "$E2E_OCC_TITLE" = "Foo Modified" ] \
    && ok "detached occurrence title = 'Foo Modified'" \
    || fail "detached occurrence title = '$E2E_OCC_TITLE'"
[ "$E2E_OCC_COLOR" = "#ff0000" ] \
    && ok "detached occurrence color = '#ff0000'" \
    || fail "detached occurrence color = '$E2E_OCC_COLOR'"
[ "$E2E_OCC_START" = "2037-07-09T13:00:00Z" ] \
    && ok "detached occurrence shifted to 13:00" \
    || fail "detached occurrence start = '$E2E_OCC_START' (expected 13:00)"

# 4. Verify LOGIN_2 has the detached occurrence with modifications
CODE=$(req "$BASE/events?start_date_time=2037-07-09T00:00:00Z&end_date_time=2037-07-09T23:59:59Z" -H "$H_AUTH_2")
check_code "E2E: LOGIN_2 sees detached occurrence" "$CODE" "200"
L2_OCC_TITLE=$(body | jq -r --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid and .title == "Foo Modified")][0].title // empty')
[ "$L2_OCC_TITLE" = "Foo Modified" ] \
    && ok "LOGIN_2 sees detached occurrence 'Foo Modified'" \
    || fail "LOGIN_2 does not see 'Foo Modified' (got '$L2_OCC_TITLE')"

# 5. Move all events: shift master +1h (12:00 -> 13:00)
CODE=$(req -X PATCH "$BASE/events/$E2E_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"date_start": "2037-07-06T13:00:00Z", "date_end": "2037-07-06T14:00:00Z"}')
check_code "E2E: move all events +1h" "$CODE" "200"

# 6. Verify organizer: all regular occurrences at 13:00, detached at 14:00 (13:00 + 1h offset)
CODE=$(req "$BASE/events?start_date_time=2037-07-06T00:00:00Z&end_date_time=2037-07-13T23:59:59Z" -H "$H_AUTH")
check_code "E2E: organizer events after shift" "$CODE" "200"
ORG_MONDAY=$(body | jq -r --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid and .title == "Foo")][0].date_start // empty' | sed 's/\.000Z$/Z/')
ORG_OCC=$(body | jq -r --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid and .title == "Foo Modified")][0].date_start // empty' | sed 's/\.000Z$/Z/')
[ "$ORG_MONDAY" = "2037-07-06T13:00:00Z" ] \
    && ok "organizer: regular occurrence shifted to 13:00" \
    || fail "organizer: regular occurrence at '$ORG_MONDAY' (expected 13:00)"
[ "$ORG_OCC" = "2037-07-09T14:00:00Z" ] \
    && ok "organizer: detached occurrence shifted to 14:00 (preserved +1h offset)" \
    || fail "organizer: detached occurrence at '$ORG_OCC' (expected 14:00)"

# 7. Verify LOGIN_2: same shift applied
CODE=$(req "$BASE/events?start_date_time=2037-07-06T00:00:00Z&end_date_time=2037-07-13T23:59:59Z" -H "$H_AUTH_2")
check_code "E2E: LOGIN_2 events after shift" "$CODE" "200"
L2_MONDAY=$(body | jq -r --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid and .title == "Foo")][0].date_start // empty' | sed 's/\.000Z$/Z/')
L2_OCC=$(body | jq -r --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid and .title == "Foo Modified")][0].date_start // empty' | sed 's/\.000Z$/Z/')
[ "$L2_MONDAY" = "2037-07-06T13:00:00Z" ] \
    && ok "LOGIN_2: regular occurrence shifted to 13:00" \
    || fail "LOGIN_2: regular occurrence at '$L2_MONDAY' (expected 13:00)"
[ "$L2_OCC" = "2037-07-09T14:00:00Z" ] \
    && ok "LOGIN_2: detached occurrence shifted to 14:00" \
    || fail "LOGIN_2: detached occurrence at '$L2_OCC' (expected 14:00)"

# 8. Delete the entire series (organizer delete cascades)
CODE=$(req -X DELETE "$BASE/events/$E2E_KEY" -H "$H_AUTH")
check_code "E2E: delete series (organizer)" "$CODE" "200"

# 9. Verify organizer: no events left
CODE=$(req "$BASE/events?start_date_time=2037-07-06T00:00:00Z&end_date_time=2037-07-20T23:59:59Z" -H "$H_AUTH")
check_code "E2E: organizer events after delete" "$CODE" "200"
ORG_REMAINING=$(body | jq --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$ORG_REMAINING" -eq 0 ] 2>/dev/null \
    && ok "organizer: no events remain after delete" \
    || fail "organizer: $ORG_REMAINING events still present"

# 10. Verify LOGIN_2: no events left
CODE=$(req "$BASE/events?start_date_time=2037-07-06T00:00:00Z&end_date_time=2037-07-20T23:59:59Z" -H "$H_AUTH_2")
check_code "E2E: LOGIN_2 events after delete" "$CODE" "200"
L2_REMAINING=$(body | jq --arg uid "$E2E_UID" '[.data.events[] | select(.uid == $uid)] | length')
[ "$L2_REMAINING" -eq 0 ] 2>/dev/null \
    && ok "LOGIN_2: no events remain after delete" \
    || fail "LOGIN_2: $L2_REMAINING events still present"

# -- 17. CONDITIONAL DELETES ---------------------------------------------------

step "66. Delete - LOGIN_1 freebusy events, tasks, and main test events"
info "Deletes all events and tasks created by LOGIN_1 during this run. Skipped without -d."

if $DO_DELETE; then
    for key in "$FB_L1_MORNING" "$FB_L1_AFTERNOON" "$FB_L1_TENTATIVE" "$FB_L1_FREE" "$FB_L1_CANCELLED" "$FB_L1_PUBLIC_TITLE" "$FB_L1_PRIVATE_TITLE"; do
        CODE=$(req -X DELETE "$BASE/events/$key" -H "$H_AUTH")
        check_code "DELETE /events/$key (L1 freebusy)" "$CODE" "200"
    done
    for key in "$EVT_KEY" "$ALLDAY_KEY" "$COMPLEX_KEY"; do
        CODE=$(req -X DELETE "$BASE/events/$key" -H "$H_AUTH")
        check_code  "DELETE /events/$key" "$CODE" "200"
        check_error "DELETE /events/$key error_code"
        GONE=$(req "$BASE/events/$key" -H "$H_AUTH")
        [ "$GONE" = "404" ] && ok "$key gone after delete (404)" || fail "$key still accessible (HTTP $GONE)"
    done
    for key in "$DAILY_KEY" "$WEEKLY_KEY" "$MONTHLY_KEY"; do
        CODE=$(req -X DELETE "$BASE/events/$key" -H "$H_AUTH")
        check_code "DELETE /events/$key" "$CODE" "200"
    done
    # Recurrence scope test artifacts: detached occurrence and split series.
    # May already be gone (cascade-deleted with their master), so 404 is acceptable.
    for key in "$OCCURRENCE_EDIT_KEY" "$SPLIT_KEY" "$SPLIT_MONTHLY_KEY" "$SHIFT_KEY" "$SHIFT_OCC_KEY" "$PROP_KEY" "$PROP_OCC_KEY"; do
        if [ -n "$key" ]; then
            CODE=$(req -X DELETE "$BASE/events/$key" -H "$H_AUTH")
            [ "$CODE" = "200" ] || [ "$CODE" = "404" ] \
                && ok "DELETE /events/$key (scope artifact) - HTTP $CODE" \
                || fail "DELETE /events/$key (scope artifact) - expected 200 or 404, got $CODE"
        fi
    done
    for key in "$TASK_KEY" "$TASK_KEY2"; do
        CODE=$(req -X DELETE "$BASE/tasks/$key" -H "$H_AUTH")
        check_code  "DELETE /tasks/$key" "$CODE" "200"
        check_error "DELETE /tasks/$key error_code"
        GONE=$(req "$BASE/tasks/$key" -H "$H_AUTH")
        [ "$GONE" = "404" ] && ok "$key gone after delete (404)" || fail "$key still accessible (HTTP $GONE)"
    done
    # Delete attendee copy before organizer copy - the organizer delete propagates per-attendee
    CODE=$(req -X DELETE "$BASE/events/$INVITE_KEY_L2" -H "$H_AUTH_2")
    check_code "DELETE /events/$INVITE_KEY_L2 (invite attendee copy)" "$CODE" "200"
    CODE=$(req -X DELETE "$BASE/events/$INVITE_KEY_L1" -H "$H_AUTH")
    check_code "DELETE /events/$INVITE_KEY_L1 (invite organizer copy)" "$CODE" "200"
    # Recurring invite - occurrence first, then attendee copy, then organizer copy
    for key in "$OCC_ATT_KEY"; do
        if [ -n "$key" ]; then
            CODE=$(req -X DELETE "$BASE/events/$key" -H "$H_AUTH_2")
            [ "$CODE" = "200" ] || [ "$CODE" = "404" ] \
                && ok "DELETE /events/$key (recurring invite occ) - HTTP $CODE" \
                || fail "DELETE /events/$key (recurring invite occ) - expected 200 or 404, got $CODE"
        fi
    done
    CODE=$(req -X DELETE "$BASE/events/$REC_INVITE_KEY_L2" -H "$H_AUTH_2")
    check_code "DELETE /events/$REC_INVITE_KEY_L2 (recurring invite attendee copy)" "$CODE" "200"
    CODE=$(req -X DELETE "$BASE/events/$REC_INVITE_KEY_L1" -H "$H_AUTH")
    check_code "DELETE /events/$REC_INVITE_KEY_L1 (recurring invite organizer copy)" "$CODE" "200"
else
    skip "DELETE LOGIN_1 events and tasks"
    info "Keys: EVT=$EVT_KEY  ALLDAY=$ALLDAY_KEY  COMPLEX=$COMPLEX_KEY"
    info "Keys: DAILY=$DAILY_KEY  WEEKLY=$WEEKLY_KEY  MONTHLY=$MONTHLY_KEY"
    info "Occurrence: $OCCURRENCE_KEY"
    info "Recurrence scope artifacts: occurrence_edit=$OCCURRENCE_EDIT_KEY  split=$SPLIT_KEY"
    info "Tasks: TASK=$TASK_KEY  TASK2=$TASK_KEY2"
    info "FreeBusy events L1: morning=$FB_L1_MORNING afternoon=$FB_L1_AFTERNOON"
    info "FreeBusy events L1: tentative=$FB_L1_TENTATIVE free=$FB_L1_FREE cancelled=$FB_L1_CANCELLED"
    info "FreeBusy events L1: public_title=$FB_L1_PUBLIC_TITLE private_title=$FB_L1_PRIVATE_TITLE"
    info "Invitation: organizer=$INVITE_KEY_L1  attendee_copy=$INVITE_KEY_L2"
    info "Recurring invite: organizer=$REC_INVITE_KEY_L1  attendee_copy=$REC_INVITE_KEY_L2  occ=$OCC_ATT_KEY"
fi

# -- 20. REMINDERS ------------------------------------------------------------

step "69. Reminders - create event with reminder in active window"
info "Creates an event whose date_start is 5 min ago and date_end is 1 hour ahead,"
info "with a 10-min-before popup reminder. trigger_at = date_start - 10min = 15 min ago -> active now."

# The title carries a per-run nonce: step 74 asserts the deleted event's reminders are gone, and a
# run without -d leaves its event alive, so a shared title would make later runs count leftovers.
REM_TITLE="Reminder Test Event $(date +%s)"

NOW_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
START_5M_AGO=$(date -u -v-5M +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "-5 minutes" +"%Y-%m-%dT%H:%M:%SZ")
END_1H_AHEAD=$(date -u -v+1H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+1 hour" +"%Y-%m-%dT%H:%M:%SZ")

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"$REM_TITLE\",
        \"date_start\": \"$START_5M_AGO\",
        \"date_end\":   \"$END_1H_AHEAD\",
        \"reminders\": [
            {\"method\": \"popup\", \"minutes_before\": 10},
            {\"method\": \"email\", \"minutes_before\": 30}
        ]
    }")
check_code  "POST /events (reminder test)" "$CODE" "201"
check_error "POST /events (reminder test) error_code"
REM_EVT_KEY=$(extract '.data.key')
info "reminder event key=$REM_EVT_KEY"


step "70. Reminders - GET /reminders returns active reminders"
info "Both popup (10 min before) and email (30 min before) should be active:"
info "  popup  trigger_at = start - 10min = 15 min ago -> active (now < date_end)"
info "  email  trigger_at = start - 30min = 35 min ago -> active (now < date_end)"

CODE=$(req "$BASE/reminders" -H "$H_AUTH")
check_code  "GET /reminders" "$CODE" "200"
check_error "GET /reminders error_code"
REM_COUNT=$(body | jq -r '.data.total_count')
[ "$REM_COUNT" -ge 2 ] && ok "reminder count >= 2 (got $REM_COUNT)" || fail "expected >= 2 reminders, got $REM_COUNT"

REM_HAS_POPUP=$(body | jq '[.data.reminders[] | select(.method == "popup")] | length')
REM_HAS_EMAIL=$(body | jq '[.data.reminders[] | select(.method == "email")] | length')
[ "$REM_HAS_POPUP" -ge 1 ] && ok "popup reminder present" || fail "no popup reminder found"
[ "$REM_HAS_EMAIL" -ge 1 ] && ok "email reminder present" || fail "no email reminder found"

REM_HAS_EVENT=$(body | jq --arg t "$REM_TITLE" '[.data.reminders[] | select(.title == $t)] | length')
[ "$REM_HAS_EVENT" -ge 1 ] && ok "reminder carries event data" || fail "reminder missing event data"

REM_HAS_MIN=$(body | jq '[.data.reminders[] | select(.minutes_before == 10)] | length')
[ "$REM_HAS_MIN" -ge 1 ] && ok "minutes_before=10 present" || fail "minutes_before=10 not found"


step "71. Reminders - GET /reminders?method=popup filters by method"
info "Only popup reminders should be returned."

CODE=$(req "$BASE/reminders?method=popup" -H "$H_AUTH")
check_code  "GET /reminders?method=popup" "$CODE" "200"
check_error "GET /reminders?method=popup error_code"
REM_ONLY_POPUP=$(body | jq '[.data.reminders[] | select(.method != "popup")] | length')
[ "$REM_ONLY_POPUP" -eq 0 ] && ok "only popup reminders returned" || fail "non-popup reminders present ($REM_ONLY_POPUP)"


step "72. Reminders - GET /reminders?lookahead=30 extends window"
info "Lookahead parameter accepted, response is valid."

CODE=$(req "$BASE/reminders?lookahead=30" -H "$H_AUTH")
check_code  "GET /reminders?lookahead=30" "$CODE" "200"
check_error "GET /reminders?lookahead=30 error_code"


step "73. Reminders - no active reminders for event in the far future"
info "Creates an event 1 year ahead with a 15-min reminder. trigger_at is in the future -> not active."

FUTURE_START=$(date -u -v+1y +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+1 year" +"%Y-%m-%dT%H:%M:%SZ")
FUTURE_END=$(date -u -v+1y -v+1H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+1 year +1 hour" +"%Y-%m-%dT%H:%M:%SZ")

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Future Event No Reminder\",
        \"date_start\": \"$FUTURE_START\",
        \"date_end\":   \"$FUTURE_END\",
        \"reminders\": [{\"method\": \"popup\", \"minutes_before\": 15}]
    }")
check_code "POST /events (future event)" "$CODE" "201"
REM_FUTURE_KEY=$(extract '.data.key')

CODE=$(req "$BASE/reminders" -H "$H_AUTH")
check_code "GET /reminders (no future)" "$CODE" "200"
REM_FUTURE_MATCH=$(body | jq "[.data.reminders[] | select(.title == \"Future Event No Reminder\")] | length")
[ "$REM_FUTURE_MATCH" -eq 0 ] && ok "future event reminder not active" || fail "future event reminder unexpectedly active"


step "74. Reminders - delete reminder event, then GET /reminders excludes it"
info "Deletes the reminder test event. Its reminders should no longer appear."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/events/$REM_EVT_KEY" -H "$H_AUTH")
    check_code "DELETE /events/$REM_EVT_KEY (reminder test)" "$CODE" "200"

    CODE=$(req "$BASE/reminders" -H "$H_AUTH")
    check_code "GET /reminders (after delete)" "$CODE" "200"
    REM_DELETED_MATCH=$(body | jq --arg t "$REM_TITLE" '[.data.reminders[] | select(.title == $t)] | length')
    [ "$REM_DELETED_MATCH" -eq 0 ] && ok "deleted event reminders gone" || fail "deleted event reminders still present"

    CODE=$(req -X DELETE "$BASE/events/$REM_FUTURE_KEY" -H "$H_AUTH")
    check_code "DELETE /events/$REM_FUTURE_KEY (future event)" "$CODE" "200"
else
    skip "DELETE reminder test events"
    info "reminder_event=$REM_EVT_KEY  future_event=$REM_FUTURE_KEY"
fi


# -- 21. EXTERNAL CALENDARS ---------------------------------------------------

ICS_URL="https://calendar.google.com/calendar/ical/8f0aaf825b126f8f3f8ae5799c3c8699bcf04b115bfee085467e19f71ba084ba%40group.calendar.google.com/private-5e54ad70f6be3e5a740648483b0469dd/basic.ics"

step "75. External calendar - create ICS subscription"
info "Creates an external ICS calendar pointing to a public Google Calendar feed."

CODE=$(req -X POST "$BASE/external-calendars" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"name\": \"Google Public ICS\",
        \"url\": \"$ICS_URL\",
        \"color\": \"#F59E0B\",
        \"sync_interval_minutes\": 30
    }")
check_code  "POST /external-calendars" "$CODE" "201"
check_error "POST /external-calendars error_code"
check_field ".data.source_type" "ics"
EXT_CAL_KEY=$(extract '.data.key')
info "external calendar key=$EXT_CAL_KEY"


step "76. External calendar - list subscriptions"
info "Verifies GET /external-calendars returns at least the newly created subscription."

CODE=$(req "$BASE/external-calendars" -H "$H_AUTH")
check_code  "GET /external-calendars" "$CODE" "200"
check_error "GET /external-calendars error_code"
EXT_COUNT=$(extract '.data.total_count')
[ "$EXT_COUNT" -ge 1 ] && ok "external calendar count >= 1 (got $EXT_COUNT)" || fail "expected >= 1, got $EXT_COUNT"


step "77. External calendar - get detail"
info "Fetches the external calendar by key."

CODE=$(req "$BASE/external-calendars/$EXT_CAL_KEY" -H "$H_AUTH")
check_code  "GET /external-calendars/$EXT_CAL_KEY" "$CODE" "200"
check_field ".data.name" "Google Public ICS"


step "78. External calendar - update name and color"
info "Renames the external calendar and changes its color."

CODE=$(req -X PUT "$BASE/external-calendars/$EXT_CAL_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Renamed ICS Feed", "color": "#EF4444"}')
check_code  "PUT /external-calendars/$EXT_CAL_KEY" "$CODE" "200"
check_field ".data.name" "Renamed ICS Feed"
check_field ".data.color" "#EF4444"


step "79. External calendar - sync (async job)"
info "POST /sync enqueues an Agent job (202); poll GET /jobs/<id> until success, then read the counters from the result. Fetches the real ICS feed."

CODE=$(req -X POST "$BASE/external-calendars/$EXT_CAL_KEY/sync" -H "$H_JSON" -H "$H_AUTH" -d '{}')
check_code  "POST /external-calendars/$EXT_CAL_KEY/sync (enqueue)" "$CODE" "202"
check_error "POST sync error_code"
SYNC_JOB_ID=$(extract '.data.job_id')
[ -n "$SYNC_JOB_ID" ] && ok "sync returned a job_id" || fail "sync returned no job_id"

JOB_STATUS=""
for _ in $(seq 1 60); do
    CODE=$(req "$BASE/jobs/$SYNC_JOB_ID" -H "$H_AUTH")
    JOB_STATUS=$(extract '.data.status')
    [ "$JOB_STATUS" = "success" ] && break
    { [ "$JOB_STATUS" = "failure" ] || [ "$JOB_STATUS" = "canceled" ]; } && break
    sleep 1
done
[ "$JOB_STATUS" = "success" ] && ok "sync job completed" || fail "sync job did not succeed (status='$JOB_STATUS')"
SYNC_INSERTED=$(extract '.data.result.inserted')
SYNC_TOTAL=$(extract '.data.result.total')
info "sync result: inserted=$SYNC_INSERTED total=$SYNC_TOTAL"
{ [ -n "$SYNC_TOTAL" ] && [ "$SYNC_TOTAL" -ge 0 ]; } && ok "sync completed (total=$SYNC_TOTAL)" || fail "sync failed (total='$SYNC_TOTAL')"


step "80. External calendar - sync status"
info "Verifies GET /sync returns completed status after a successful sync."

CODE=$(req "$BASE/external-calendars/$EXT_CAL_KEY/sync" -H "$H_AUTH")
check_code  "GET /external-calendars/$EXT_CAL_KEY/sync" "$CODE" "200"
check_field ".data.sync_status" "completed"


step "81. External calendar - events visible after sync"
info "Verifies that synced events appear in GET /events for the ICS calendar."

NOW_DATE=$(date -u +"%Y-%m-%dT00:00:00Z")
END_DATE=$(date -u -v+30d +"%Y-%m-%dT23:59:59Z" 2>/dev/null || date -u -d "+30 days" +"%Y-%m-%dT23:59:59Z")
CODE=$(req "$BASE/calendars/$EXT_CAL_KEY/events?start_date_time=$NOW_DATE&end_date_time=$END_DATE" -H "$H_AUTH")
check_code "GET /calendars/$EXT_CAL_KEY/events" "$CODE" "200"
EXT_EVT_COUNT=$(extract '.data.total_count')
info "events in ICS calendar: $EXT_EVT_COUNT"
[ "$EXT_EVT_COUNT" -ge 0 ] && ok "events accessible (count=$EXT_EVT_COUNT)" || fail "events not accessible"


step "82. External calendar - write rejected on ICS mirror"
info "Verifies that creating an event on an ICS calendar is rejected (read-only mirror)."

CODE=$(req -X POST "$BASE/calendars/$EXT_CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Should fail",
        "date_start": "2037-06-01T10:00:00Z",
        "date_end": "2037-06-01T11:00:00Z"
    }')
[ "$CODE" != "201" ] && ok "write rejected on ICS mirror (HTTP $CODE)" || fail "write should have been rejected, got HTTP $CODE"


step "83. External calendar - delete"
info "Deletes the external calendar. Skipped without -d."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/external-calendars/$EXT_CAL_KEY" -H "$H_AUTH")
    check_code "DELETE /external-calendars/$EXT_CAL_KEY" "$CODE" "200"
else
    skip "DELETE external calendar $EXT_CAL_KEY"
fi


# -- 22. EXPORT / IMPORT -------------------------------------------------------

step "84. Export/Import - create dedicated calendar"
info "Creates a fresh calendar used only by the export/import round-trip."

CODE=$(req -X POST "$BASE/calendars" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Export Roundtrip", "color": "#10B981", "timezone": "UTC"}')
check_code "POST /calendars (export roundtrip)" "$CODE" "201"
EXP_CAL_KEY=$(extract '.data.key')
check_not_empty '.data.key'


step "85. Export/Import - populate with simple, all-day and recurring events"
info "Creates three distinct events whose UIDs we will later look for in the export."

EXP_UID_SIMPLE="exp-simple-$RANDOM@example.com"
CODE=$(req -X POST "$BASE/calendars/$EXP_CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$EXP_UID_SIMPLE\",
        \"title\": \"Roundtrip Simple\",
        \"date_start\": \"2037-07-01T09:00:00Z\",
        \"date_end\":   \"2037-07-01T10:00:00Z\"
    }")
check_code "POST simple event" "$CODE" "201"
EXP_KEY_SIMPLE=$(extract '.data.key')

EXP_UID_ALLDAY="exp-allday-$RANDOM@example.com"
CODE=$(req -X POST "$BASE/calendars/$EXP_CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$EXP_UID_ALLDAY\",
        \"title\": \"Roundtrip Allday\",
        \"date_start\": \"2037-07-02T00:00:00Z\",
        \"date_end\":   \"2037-07-03T00:00:00Z\",
        \"all_day\": true
    }")
check_code "POST all-day event" "$CODE" "201"
EXP_KEY_ALLDAY=$(extract '.data.key')

EXP_UID_RRULE="exp-rrule-$RANDOM@example.com"
CODE=$(req -X POST "$BASE/calendars/$EXP_CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$EXP_UID_RRULE\",
        \"title\": \"Roundtrip Weekly\",
        \"date_start\": \"2037-07-06T08:00:00Z\",
        \"date_end\":   \"2037-07-06T09:00:00Z\",
        \"recurrence_rule\": {\"frequency\": \"weekly\", \"count\": 4}
    }")
check_code "POST recurring event" "$CODE" "201"
EXP_KEY_RRULE=$(extract '.data.key')


step "86. Export/Import - run the async export job and verify content"
info "GET /export enqueues an Agent job; poll GET /jobs/<id> until success, then download the result."

EXP_ICS_FILE=$(mktemp)
# Keep the original TMPFILE cleanup: a bare EXIT trap here would replace it, not add to it.
trap 'rm -f "$TMPFILE" "$EXP_ICS_FILE"' EXIT

# 1. Enqueue the export - returns a job_id (202), not the ICS.
CODE=$(req "$BASE/calendars/$EXP_CAL_KEY/export" -H "$H_AUTH")
check_code "GET /calendars/$EXP_CAL_KEY/export (enqueue)" "$CODE" "202"
EXP_JOB_ID=$(extract '.data.job_id')
[ -n "$EXP_JOB_ID" ] && ok "export returned a job_id" || fail "export returned no job_id"

# 2. Poll the job status until it reaches a terminal state (worker must be running).
JOB_STATUS=""
for _ in $(seq 1 60); do
    CODE=$(req "$BASE/jobs/$EXP_JOB_ID" -H "$H_AUTH")
    JOB_STATUS=$(extract '.data.status')
    [ "$JOB_STATUS" = "success" ] && break
    { [ "$JOB_STATUS" = "failure" ] || [ "$JOB_STATUS" = "canceled" ]; } && break
    sleep 1
done
[ "$JOB_STATUS" = "success" ] && ok "export job completed" || fail "export job did not succeed (status='$JOB_STATUS')"

# 3. Download the produced ICS from the job result.
CODE=$(curl -s -o "$EXP_ICS_FILE" -w "%{http_code}" "$BASE/jobs/$EXP_JOB_ID/result?download=true" -H "$H_AUTH")
check_code "GET /jobs/$EXP_JOB_ID/result" "$CODE" "200"

grep -q "BEGIN:VCALENDAR" "$EXP_ICS_FILE" && ok "ICS has BEGIN:VCALENDAR" || fail "ICS missing BEGIN:VCALENDAR"
grep -q "END:VCALENDAR"   "$EXP_ICS_FILE" && ok "ICS has END:VCALENDAR"   || fail "ICS missing END:VCALENDAR"
grep -qF "$EXP_UID_SIMPLE" "$EXP_ICS_FILE" && ok "ICS contains simple UID"  || fail "ICS missing simple UID"
grep -qF "$EXP_UID_ALLDAY" "$EXP_ICS_FILE" && ok "ICS contains all-day UID" || fail "ICS missing all-day UID"
grep -qF "$EXP_UID_RRULE"  "$EXP_ICS_FILE" && ok "ICS contains recurring UID" || fail "ICS missing recurring UID"
grep -q  "RRULE:FREQ=WEEKLY" "$EXP_ICS_FILE" && ok "ICS preserves the RRULE master" || fail "RRULE master not in export (occurrences expanded?)"

# The job result is served inline by default; ?download=true adds the attachment header.
INLINE_HEADERS=$(curl -s -D - -o /dev/null "$BASE/jobs/$EXP_JOB_ID/result" -H "$H_AUTH")
echo "$INLINE_HEADERS" | grep -qi "Content-Disposition: attachment" \
    && fail "inline result should NOT carry attachment header" \
    || ok "inline result served without attachment header"

DL_HEADERS=$(curl -s -D - -o /dev/null "$BASE/jobs/$EXP_JOB_ID/result?download=true" -H "$H_AUTH")
echo "$DL_HEADERS" | grep -qi "Content-Disposition: attachment" \
    && ok "download=true adds attachment header" \
    || fail "download=true should add Content-Disposition: attachment"


step "87. Export/Import - delete every event of the calendar"
info "Removes the three events so the calendar is empty before importing back."

CODE=$(req -X DELETE "$BASE/events/$EXP_KEY_SIMPLE" -H "$H_AUTH")
check_code "DELETE simple event" "$CODE" "200"
CODE=$(req -X DELETE "$BASE/events/$EXP_KEY_ALLDAY" -H "$H_AUTH")
check_code "DELETE all-day event" "$CODE" "200"
CODE=$(req -X DELETE "$BASE/events/$EXP_KEY_RRULE" -H "$H_AUTH")
check_code "DELETE recurring event" "$CODE" "200"

CODE=$(req "$BASE/calendars/$EXP_CAL_KEY/events?start_date_time=2037-07-01T00:00:00Z&end_date_time=2037-07-31T00:00:00Z" -H "$H_AUTH")
check_code "GET events (after deletes)" "$CODE" "200"
EXP_REMAINING=$(body | jq -r '.data.events | length')
[ "$EXP_REMAINING" = "0" ] && ok "calendar empty after deletes" || fail "calendar still has $EXP_REMAINING event(s) after deletes"


step "88. Export/Import - re-import the .ics file (async job)"
info "POST /import enqueues an Agent job; poll GET /jobs/<id> until success, then read the counters from the result."

# 1. Enqueue the import - multipart upload returns a job_id (202), not the counters.
CODE=$(req -X POST "$BASE/calendars/$EXP_CAL_KEY/import" \
    -H "$H_AUTH" \
    -F "file=@$EXP_ICS_FILE;type=text/calendar")
check_code "POST /calendars/$EXP_CAL_KEY/import (enqueue)" "$CODE" "202"
check_error "import error_code"
IMP_JOB_ID=$(extract '.data.job_id')
[ -n "$IMP_JOB_ID" ] && ok "import returned a job_id" || fail "import returned no job_id"

# 2. Poll the job status until it reaches a terminal state (worker must be running).
JOB_STATUS=""
for _ in $(seq 1 60); do
    CODE=$(req "$BASE/jobs/$IMP_JOB_ID" -H "$H_AUTH")
    JOB_STATUS=$(extract '.data.status')
    [ "$JOB_STATUS" = "success" ] && break
    { [ "$JOB_STATUS" = "failure" ] || [ "$JOB_STATUS" = "canceled" ]; } && break
    sleep 1
done
[ "$JOB_STATUS" = "success" ] && ok "import job completed" || fail "import job did not succeed (status='$JOB_STATUS')"

# 3. The import counters live in the job result.
IMP_INSERTED=$(extract '.data.result.inserted')
IMP_DELETED=$(extract '.data.result.deleted')
[ "$IMP_INSERTED" = "3" ] && ok "import inserted 3 events" || fail "import inserted $IMP_INSERTED (expected 3)"
[ "$IMP_DELETED" = "0" ] && ok "import did not delete anything" || fail "import unexpectedly deleted $IMP_DELETED row(s)"


step "88b. Export/Import - a malformed .ics makes the import job fail"
info "Content is not validated synchronously, so the upload is accepted (202); the worker job must then end in 'failure' (parse error), exercising the Agent failure path end-to-end and leaving the calendar untouched."

BAD_ICS_FILE=$(mktemp)
printf 'this is definitely not an ics file\n' > "$BAD_ICS_FILE"

# 0. Snapshot the calendar before the failed import (the range query expands RRULE
# occurrences, so the count is not the number of master events).
CODE=$(req "$BASE/calendars/$EXP_CAL_KEY/events?start_date_time=2037-07-01T00:00:00Z&end_date_time=2037-07-31T00:00:00Z" -H "$H_AUTH")
BAD_BEFORE=$(body | jq -r '.data.events | length')

# 1. Enqueue: the malformed payload is accepted (parsing happens worker-side).
CODE=$(req -X POST "$BASE/calendars/$EXP_CAL_KEY/import" \
    -H "$H_AUTH" \
    -F "file=@$BAD_ICS_FILE;type=text/calendar")
check_code "POST /import (malformed, enqueue)" "$CODE" "202"
BAD_JOB_ID=$(extract '.data.job_id')
[ -n "$BAD_JOB_ID" ] && ok "malformed import returned a job_id" || fail "malformed import returned no job_id"

# 2. Poll until terminal: this one must reach 'failure', not 'success'.
JOB_STATUS=""
for _ in $(seq 1 60); do
    CODE=$(req "$BASE/jobs/$BAD_JOB_ID" -H "$H_AUTH")
    JOB_STATUS=$(extract '.data.status')
    { [ "$JOB_STATUS" = "failure" ] || [ "$JOB_STATUS" = "success" ] || [ "$JOB_STATUS" = "canceled" ]; } && break
    sleep 1
done
[ "$JOB_STATUS" = "failure" ] && ok "malformed import job failed as expected" || fail "malformed import status='$JOB_STATUS' (expected failure)"

# 3. The failure must surface an error message on the job.
BAD_JOB_ERROR=$(extract '.data.error')
[ -n "$BAD_JOB_ERROR" ] && ok "failed job exposes an error message" || fail "failed job has no error message"

# 4. A failed import must not touch the calendar (parse fails before any write).
CODE=$(req "$BASE/calendars/$EXP_CAL_KEY/events?start_date_time=2037-07-01T00:00:00Z&end_date_time=2037-07-31T00:00:00Z" -H "$H_AUTH")
BAD_AFTER=$(body | jq -r '.data.events | length')
[ "$BAD_AFTER" = "$BAD_BEFORE" ] && ok "calendar unchanged after failed import ($BAD_AFTER events)" || fail "calendar changed after failed import ($BAD_BEFORE -> $BAD_AFTER)"

rm -f "$BAD_ICS_FILE"


step "89. Export/Import - verify the three events are back"
info "Re-fetches the calendar events and checks each original UID is present."

CODE=$(req "$BASE/calendars/$EXP_CAL_KEY/events?start_date_time=2037-07-01T00:00:00Z&end_date_time=2037-07-31T00:00:00Z" -H "$H_AUTH")
check_code "GET events (after import)" "$CODE" "200"

info "Original UIDs: $EXP_UID_SIMPLE | $EXP_UID_ALLDAY | $EXP_UID_RRULE"
info "Re-fetched UIDs: $(body | jq -r '[.data.events[].uid] | unique | join(" | ")')"
info "Re-fetched titles: $(body | jq -r '[.data.events[].title] | unique | join(" | ")')"

SIMPLE_BACK=$(body  | jq -r --arg uid "$EXP_UID_SIMPLE" '[.data.events[] | select(.uid == $uid)] | length')
ALLDAY_BACK=$(body  | jq -r --arg uid "$EXP_UID_ALLDAY" '[.data.events[] | select(.uid == $uid)] | length')
RRULE_BACK=$(body   | jq -r --arg uid "$EXP_UID_RRULE"  '[.data.events[] | select(.uid == $uid)] | length')
[ "$SIMPLE_BACK" -ge 1 ] && ok "simple event is back"     || fail "simple event missing after import"
[ "$ALLDAY_BACK" -ge 1 ] && ok "all-day event is back"    || fail "all-day event missing after import"
[ "$RRULE_BACK"  -ge 1 ] && ok "recurring event is back"  || fail "recurring event missing after import (expected >= 1 occurrence)"

# The re-imported event becomes owned by the importing user (IMPORT_REWRITES_OWNERSHIP=True)
NEW_ORGANIZER=$(body | jq -r --arg uid "$EXP_UID_SIMPLE" '[.data.events[] | select(.uid == $uid)][0].organizer.email // empty')
[ "$NEW_ORGANIZER" = "$USER" ] && ok "importer is the new organizer ($USER)" || fail "organizer rewrite - expected $USER, got '$NEW_ORGANIZER'"


step "90. Export/Import - cleanup roundtrip calendar"
info "Deletes the dedicated calendar. Skipped without -d."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/calendars/$EXP_CAL_KEY" -H "$H_AUTH")
    check_code "DELETE /calendars/$EXP_CAL_KEY" "$CODE" "200"
else
    skip "DELETE roundtrip calendar $EXP_CAL_KEY"
fi


step "91. Public subscription - create a calendar with one event"
info "Sets up a dedicated calendar to activate a public .ics subscription URL on."

CODE=$(req -X POST "$BASE/calendars" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Public Subscription Cal", "color": "#22aa55"}')
check_code "POST /calendars (subscription)" "$CODE" "201"
SUB_CAL_KEY=$(extract '.data.key')

SUB_UID="sub-evt-$RANDOM@example.com"
CODE=$(req -X POST "$BASE/calendars/$SUB_CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$SUB_UID\",
        \"title\": \"PublicEvent\",
        \"date_start\": \"2037-07-10T09:00:00Z\",
        \"date_end\":   \"2037-07-10T10:00:00Z\"
    }")
check_code "POST event (subscription)" "$CODE" "201"


step "92. Public subscription - enable and capture the public URL"
info "POST /calendars/.../subscription generates a unique token and returns the public URL."

CODE=$(req -X POST "$BASE/calendars/$SUB_CAL_KEY/subscription" -H "$H_JSON" -H "$H_AUTH" -d '{}')
check_code "POST /calendars/$SUB_CAL_KEY/subscription" "$CODE" "200"
check_error "enable subscription error_code"
SUB_TOKEN=$(extract '.data.share_token')
SUB_URL=$(extract '.data.public_url')
[ -n "$SUB_TOKEN" ] && ok "share_token returned (${#SUB_TOKEN} chars)" || fail "share_token missing"
[ "${#SUB_TOKEN}" -ge 32 ] && ok "share_token is long enough to be unguessable" || fail "share_token too short (${#SUB_TOKEN} chars)"
[ -n "$SUB_URL" ] && ok "public_url returned: $SUB_URL" || fail "public_url missing"


step "93. Public subscription - GET calendar exposes the public URL"
info "Confirms the active subscription URL is reflected on the calendar resource."

CODE=$(req "$BASE/calendars/$SUB_CAL_KEY" -H "$H_AUTH")
check_code "GET /calendars/$SUB_CAL_KEY" "$CODE" "200"
GET_URL=$(extract '.data.public_url')
[ "$GET_URL" = "$SUB_URL" ] && ok "GET calendar returns the same public_url" || fail "public_url mismatch (got '$GET_URL')"


step "94. Public subscription - fetch the public URL anonymously"
info "Calls the public URL with NO Authorization header. Must return text/calendar with the event."

PUB_BODY=$(mktemp)
PUB_HEADERS=$(curl -s -D - -o "$PUB_BODY" -w "%{http_code}" "$SUB_URL")
PUB_CODE="${PUB_HEADERS##*$'\n'}"
check_code "GET public URL (anonymous)" "$PUB_CODE" "200"
echo "$PUB_HEADERS" | grep -qi "Content-Type: text/calendar" \
    && ok "public response is text/calendar" \
    || fail "public response not text/calendar"
grep -q  "BEGIN:VCALENDAR" "$PUB_BODY" && ok "public ICS has BEGIN:VCALENDAR" || fail "public ICS missing BEGIN:VCALENDAR"
grep -qF "$SUB_UID"        "$PUB_BODY" && ok "public ICS contains the event UID" || fail "public ICS missing event UID"
rm -f "$PUB_BODY"


step "95. Public subscription - unknown token returns 404"
info "A random/expired token must not leak any data."

BAD_URL="${SUB_URL%/*}/deadbeefdeadbeefdeadbeefdeadbeef"
BAD_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BAD_URL")
check_code "GET public URL (unknown token)" "$BAD_CODE" "404"


step "96. Public subscription - disable and verify the URL stops working"
info "DELETE /calendars/.../subscription clears the token; the old URL must 404 afterwards."

CODE=$(req -X DELETE "$BASE/calendars/$SUB_CAL_KEY/subscription" -H "$H_AUTH")
check_code "DELETE /calendars/$SUB_CAL_KEY/subscription" "$CODE" "200"
check_error "disable subscription error_code"
OFF_URL=$(extract '.data.public_url')
[ -z "$OFF_URL" ] && ok "public_url cleared after disable" || fail "public_url still present after disable: $OFF_URL"

GONE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SUB_URL")
check_code "GET old public URL after disable" "$GONE_CODE" "404"


step "97. Public subscription - cleanup calendar"
info "Deletes the dedicated subscription calendar. Skipped without -d."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/calendars/$SUB_CAL_KEY" -H "$H_AUTH")
    check_code "DELETE /calendars/$SUB_CAL_KEY" "$CODE" "200"
else
    skip "DELETE subscription calendar $SUB_CAL_KEY"
fi


step "98. Calendar defaults - create calendar with new-event preferences"
info "include_in_freebusy=false plus default duration/alarm/type. All four must round-trip in the response."

CODE=$(req -X POST "$BASE/calendars" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "name": "Defaults Calendar",
        "timezone": "Europe/Paris",
        "include_in_freebusy": false,
        "default_event_duration_min": 45,
        "default_alarm_duration_min": 25,
        "default_type": "private"
    }')
check_code  "POST /calendars (defaults)" "$CODE" "201"
check_error "POST /calendars (defaults) error_code"
# jq's `//` (used by check_field) treats false like null, so assert booleans with a raw read.
INC_FB=$(body | jq -r '.data.include_in_freebusy')
[ "$INC_FB" = "false" ] && ok ".data.include_in_freebusy = 'false'" || fail ".data.include_in_freebusy - expected 'false', got '$INC_FB'"
check_field ".data.default_event_duration_min" "45"
check_field ".data.default_alarm_duration_min" "25"
check_field ".data.default_type"               "private"
DEF_CAL_KEY=$(extract '.data.key')
info "Defaults calendar key: $DEF_CAL_KEY"

# The free/busy exclusion/inclusion checks below are written as DELTAS against this baseline, not as
# absolute counts: re-running without -d leaves events in the DB, so an absolute "== 0 / == 1" would
# false-fail on the next run. The delta still catches a real exclusion bug, since a leaked excluded
# event changes it.
#
# The delta alone is not enough though, so the day has to be fresh on every run. FreeBusyEngine
# merges overlapping periods of the same type, so a run landing on a day a previous run already used
# creates the very same 11:00-12:00 slot, the two collapse into one period, and the expected "+1"
# never materializes. A day derived from the clock rather than from the PID keeps the space wide
# enough for that not to happen: 2027 + PID % 70 gave 70 candidates, and collisions were routine
# after a handful of runs. Years stay past the 2037 fixtures so the two sets never meet.
FB_NONCE=$(date +%s)
FB_DATE=$(printf '%04d-%02d-%02d' \
    "$(( 2040 + FB_NONCE % 300 ))" \
    "$(( (FB_NONCE / 300) % 12 + 1 ))" \
    "$(( (FB_NONCE / 60) % 28 + 1 ))")
CODE=$(req -X POST "$BASE/freebusy" -H "$H_JSON" -H "$H_AUTH" \
    -d "{\"target_uids\": [\"$LOGIN_1\"], \"start\": \"${FB_DATE}T00:00:00Z\", \"end\": \"${FB_DATE}T23:59:59Z\"}")
FB_BASE=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
info "Free/busy baseline on $FB_DATE before this run adds events: $FB_BASE busy period(s)"


step "99. Calendar defaults - new event inherits duration, type and alarm offset"
info "Event sent without date_end, without visibility, with an alarm lacking minutes_before. The server fills all three from the calendar defaults."

CODE=$(req -X POST "$BASE/calendars/$DEF_CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Inherits Defaults\",
        \"date_start\": \"${FB_DATE}T09:00:00Z\",
        \"reminders\": [{\"method\": \"popup\"}]
    }")
check_code  "POST /events (defaults applied)" "$CODE" "201"
check_error "POST /events (defaults applied) error_code"
DEND=$(extract '.data.date_end')
case "$DEND" in
    ${FB_DATE}T09:45:00*) ok "date_end derived from default duration ($DEND)" ;;
    *) fail "date_end not derived from default duration - got '$DEND' (expected ${FB_DATE}T09:45:00*)" ;;
esac
check_field ".data.visibility"                  "private"
check_field ".data.reminders[0].minutes_before" "25"
DEF_EVT_KEY=$(extract '.data.key')
info "Defaults event key: $DEF_EVT_KEY"


step "100. Calendar defaults - free/busy excludes an include_in_freebusy=false calendar"
info "The event added in step 99 lives in the excluded calendar, so the busy-period count must not change versus the baseline."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"${FB_DATE}T00:00:00Z\",
        \"end\":   \"${FB_DATE}T23:59:59Z\"
    }")
check_code  "POST /freebusy (exclusion)" "$CODE" "200"
check_error "POST /freebusy (exclusion) error_code"
FB_EXCL=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
[ "$FB_EXCL" = "$FB_BASE" ] && ok "excluded calendar adds no busy period (still $FB_BASE)" || fail "excluded calendar leaked a period (baseline $FB_BASE -> $FB_EXCL)"


step "101. Calendar defaults - free/busy still reflects an included calendar"
info "An event the same day in the main (included) calendar must appear, proving the exclusion is per-calendar."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Counts In FreeBusy\",
        \"date_start\": \"${FB_DATE}T11:00:00Z\",
        \"date_end\":   \"${FB_DATE}T12:00:00Z\",
        \"show_as\": \"busy\"
    }")
check_code "POST /events (included calendar)" "$CODE" "201"
INCL_EVT_KEY=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"${FB_DATE}T00:00:00Z\",
        \"end\":   \"${FB_DATE}T23:59:59Z\"
    }")
check_code "POST /freebusy (inclusion)" "$CODE" "200"
FB_INCL=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
FB_EXPECTED=$((FB_EXCL + 1))
[ "$FB_INCL" = "$FB_EXPECTED" ] && ok "the included calendar's event adds exactly one busy period ($FB_EXCL -> $FB_INCL)" || fail "expected one more busy period than the excluded case ($FB_EXPECTED), got $FB_INCL"


step "102. Calendar defaults - cleanup"
info "Deletes the defaults calendar (cascades its event) and the included-calendar event. Skipped without -d."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/events/$INCL_EVT_KEY" -H "$H_AUTH")
    check_code "DELETE /events/$INCL_EVT_KEY (included)" "$CODE" "200"
    CODE=$(req -X DELETE "$BASE/calendars/$DEF_CAL_KEY" -H "$H_AUTH")
    check_code "DELETE /calendars/$DEF_CAL_KEY (defaults)" "$CODE" "200"
else
    skip "DELETE defaults calendar $DEF_CAL_KEY and included event $INCL_EVT_KEY"
fi


step "103. Recurring invite - accepting one occurrence must not leak to the master PARTSTAT"
info "LOGIN_1 invites LOGIN_2 to a daily series; LOGIN_2 accepts a SINGLE occurrence (recurrence_id).
  Regression guard: the organizer's master must keep LOGIN_2 = needs-action (per-occurrence PARTSTAT
  must not flip the whole series)."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Daily Invite\",
        \"date_start\": \"2037-08-03T09:00:00Z\",
        \"date_end\":   \"2037-08-03T10:00:00Z\",
        \"recurrence_rule\": {\"frequency\": \"daily\", \"count\": 5, \"interval\": 1},
        \"attendees\": [{\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"}]
    }")
check_code  "POST recurring invite" "$CODE" "201"
REC_KEY_L1=$(extract '.data.key')
REC_UID=$(extract '.data.uid')

CODE=$(req "$BASE/events?start_date_time=2037-08-01T00:00:00Z&end_date_time=2037-08-10T23:59:59Z" -H "$H_AUTH_2")
REC_KEY_L2=$(body | jq -r --arg uid "$REC_UID" '[.data.events[] | select(.uid == $uid)][0].key // empty')

if [ -n "$REC_KEY_L2" ]; then
    CODE=$(req -X POST "$BASE/events/$REC_KEY_L2/attendance" \
        -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"status": "accepted", "sequence": 0, "recurrence_id": "2037-08-05T09:00:00Z"}')
    check_code "POST attendance (single occurrence)" "$CODE" "200"
    OCC_STATUS=$(body | jq -r --arg e "$LOGIN_2" '.data.attendees[] | select(.email == $e) | .status // empty')
    [ "$OCC_STATUS" = "accepted" ] \
        && ok "the accepted occurrence shows LOGIN_2 = accepted" \
        || fail "occurrence status = '$OCC_STATUS' (expected accepted)"

    # The organizer's master must NOT have been flipped to accepted.
    CODE=$(req "$BASE/events/$REC_KEY_L1" -H "$H_AUTH")
    MASTER_STATUS=$(body | jq -r --arg e "$LOGIN_2" '.data.attendees[] | select(.email == $e) | .status // empty')
    [ "$MASTER_STATUS" = "needs-action" ] \
        && ok "organizer master keeps LOGIN_2 = needs-action (no leak)" \
        || fail "organizer master shows LOGIN_2 = '$MASTER_STATUS' (expected needs-action)"
else
    skip "recurring invite occurrence test (LOGIN_2 copy not found)"
fi


step "104. Recurring invite - attendee adds a reminder scoped to an occurrence (no 403)"
info "LOGIN_2 (attendee) adds a personal reminder while the UI scopes to a single occurrence
  (recurrence_id + occurrence date). Regression guard: must be accepted (200, not S000618); the
  reminder lands on LOGIN_2's series, and the organizer's content is untouched."

if [ -n "$REC_KEY_L2" ]; then
    CODE=$(req -X PATCH "$BASE/events/$REC_KEY_L2" \
        -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"recurrence_id": "2037-08-04T09:00:00Z", "date_start": "2037-08-04T09:00:00Z", "date_end": "2037-08-04T10:00:00Z", "reminders": [{"method": "popup", "minutes_before": 15}]}')
    check_code  "attendee reminder on occurrence accepted" "$CODE" "200"
    check_error "attendee reminder error_code"
    REM_COUNT=$(body | jq -r '.data.reminders | length')
    [ "$REM_COUNT" = "1" ] \
        && ok "reminder applied on LOGIN_2 copy" \
        || fail "reminder count=$REM_COUNT (expected 1)"

    # The attendee must still be blocked from changing organizer content (e.g. moving the series).
    CODE=$(req -X PATCH "$BASE/events/$REC_KEY_L2" \
        -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"date_start": "2037-09-01T09:00:00Z", "date_end": "2037-09-01T10:00:00Z"}')
    check_code "attendee content change still rejected" "$CODE" "403"
else
    skip "attendee reminder test (no LOGIN_2 copy)"
fi


step "105. THISANDFUTURE reschedule - reminders carry to the new series (organizer + attendee)"
info "LOGIN_1 has a daily series with its own reminder and invites LOGIN_2, who adds their own reminder.
  LOGIN_1 reschedules this-and-following from occ 3. Regression guard: the new series must keep the
  organizer's reminder AND the attendee's reminder (the split must not drop them)."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"TF Reminder Series\",
        \"date_start\": \"2037-10-01T09:00:00Z\",
        \"date_end\":   \"2037-10-01T10:00:00Z\",
        \"recurrence_rule\": {\"frequency\": \"daily\", \"count\": 5, \"interval\": 1},
        \"reminders\": [{\"method\": \"popup\", \"minutes_before\": 30}],
        \"attendees\": [{\"email\": \"$LOGIN_2\", \"name\": \"User Two\", \"status\": \"needs-action\"}]
    }")
check_code "POST TF series" "$CODE" "201"
TF_KEY_L1=$(extract '.data.key')
TF_UID=$(extract '.data.uid')

CODE=$(req "$BASE/events?start_date_time=2037-10-01T00:00:00Z&end_date_time=2037-10-01T23:59:59Z" -H "$H_AUTH_2")
TF_KEY_L2=$(body | jq -r --arg uid "$TF_UID" '[.data.events[] | select(.uid == $uid)][0].key // empty')

if [ -n "$TF_KEY_L2" ]; then
    CODE=$(req -X PATCH "$BASE/events/$TF_KEY_L2" -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"reminders": [{"method": "popup", "minutes_before": 10}]}')
    check_code "LOGIN_2 sets own reminder on the series" "$CODE" "200"

    # LOGIN_1 reschedules this-and-following from occ 3 (09:00 -> 11:00). The response is the new
    # master (new uid), so we track it to query the exact new series and avoid stale runs.
    CODE=$(req -X PATCH "$BASE/events/$TF_KEY_L1" -H "$H_JSON" -H "$H_AUTH" \
        -d '{"recurrence_id": "2037-10-03T09:00:00Z", "recurrence_range": "THISANDFUTURE", "date_start": "2037-10-03T11:00:00Z", "date_end": "2037-10-03T12:00:00Z"}')
    check_code "LOGIN_1 reschedule this-and-following" "$CODE" "200"
    TF_NEW_UID=$(extract '.data.uid')

    # The organizer's new series keeps the organizer's reminder (read straight from the response).
    L1_REM=$(body | jq -r '.data.reminders | length')
    [ "$L1_REM" -ge 1 ] \
        && ok "organizer new series keeps its reminder" \
        || fail "organizer new series lost its reminder (count=$L1_REM)"

    # The attendee's copy of the new series (same new uid) keeps the attendee's own reminder.
    CODE=$(req "$BASE/events?start_date_time=2037-10-03T00:00:00Z&end_date_time=2037-10-06T23:59:59Z" -H "$H_AUTH_2")
    L2_REM=$(body | jq -r --arg uid "$TF_NEW_UID" '[.data.events[] | select(.uid == $uid)][0].reminders | length // 0')
    [ "$L2_REM" -ge 1 ] \
        && ok "attendee new series keeps their reminder" \
        || fail "attendee new series lost their reminder (count=$L2_REM)"
else
    skip "TF reminder series test (LOGIN_2 copy not found)"
fi


step "106. Attendee reminder PATCH - minimal vs full-body on a recurring event"
info "A full body whose date_start echoes an occurrence (not the master) reads as a content change -> 403.
  The same reminder change sent as a MINIMAL patch (only the changed field) is accepted -> 200. This is
  why the test UI sends only the changed fields (REJECT_ATTENDEE_CONTENT_CHANGE stays strict)."

if [ -n "$REC_KEY_L2" ]; then
    # Full body carrying a divergent date_start (master is 2037-08-03) - looks like a move -> 403.
    CODE=$(req -X PATCH "$BASE/events/$REC_KEY_L2" -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"date_start": "2037-08-06T09:00:00Z", "date_end": "2037-08-06T10:00:00Z", "reminders": [{"method": "popup", "minutes_before": 5}]}')
    check_code "full-body divergent date rejected" "$CODE" "403"

    # Minimal patch - only the changed field - is accepted.
    CODE=$(req -X PATCH "$BASE/events/$REC_KEY_L2" -H "$H_JSON" -H "$H_AUTH_2" \
        -d '{"reminders": [{"method": "popup", "minutes_before": 5}]}')
    check_code "minimal reminder patch accepted" "$CODE" "200"
else
    skip "minimal patch test (no LOGIN_2 copy)"
fi


# Deleting LOGIN_2 and LOGIN_3 calendars happens at the very end, next to step 68: later steps still
# invite LOGIN_2, and an attendee with no calendar has nowhere to receive the propagated copy.

step "N1. Negative - authentication required (401)"
info "A protected endpoint must reject a request that carries no bearer token."

CODE=$(req "$BASE/calendars")
check_code "GET /calendars without token" "$CODE" "401"
# NOTE: a malformed token (e.g. "Bearer garbage") currently returns 500, not 401, because the auth
# voucher only catches ExpiredSignatureError. Not asserted here - it is an auth-layer bug, not a
# calendar one. See the report to the auth owner.


step "N2. Negative - tenant isolation (other user's resources resolve to 404)"
info "LOGIN_1 creates an event; LOGIN_2 must not reach it (or LOGIN_1's calendar) by key - the lookup is scoped to the caller's own calendars, so it is a plain 404, never another user's data."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Private L1", "date_start": "2037-08-01T09:00:00Z", "date_end": "2037-08-01T10:00:00Z"}')
check_code "POST /events (LOGIN_1 private)" "$CODE" "201"
NEG_EVT=$(extract '.data.key')

CODE=$(req "$BASE/events/$NEG_EVT" -H "$H_AUTH_2")
check_code "GET LOGIN_1 event as LOGIN_2 -> 404" "$CODE" "404"

CODE=$(req -X PATCH "$BASE/events/$NEG_EVT" -H "$H_JSON" -H "$H_AUTH_2" -d '{"title": "hijack"}')
check_code "PATCH LOGIN_1 event as LOGIN_2 -> 404" "$CODE" "404"

CODE=$(req -X DELETE "$BASE/events/$NEG_EVT" -H "$H_AUTH_2")
check_code "DELETE LOGIN_1 event as LOGIN_2 -> 404" "$CODE" "404"

CODE=$(req "$BASE/calendars/$CAL_KEY" -H "$H_AUTH_2")
check_code "GET LOGIN_1 calendar as LOGIN_2 -> 404" "$CODE" "404"


step "N3. Negative - unknown keys on write verbs (404)"
info "PATCH/DELETE/GET against keys that do not exist must 404, not 500 or a silent success."

CODE=$(req -X PATCH "$BASE/events/does-not-exist" -H "$H_JSON" -H "$H_AUTH" -d '{"title": "x"}')
check_code "PATCH /events/unknown" "$CODE" "404"
CODE=$(req -X DELETE "$BASE/events/does-not-exist" -H "$H_AUTH")
check_code "DELETE /events/unknown" "$CODE" "404"
CODE=$(req "$BASE/tasks/does-not-exist" -H "$H_AUTH")
check_code "GET /tasks/unknown" "$CODE" "404"
CODE=$(req -X PATCH "$BASE/tasks/does-not-exist" -H "$H_JSON" -H "$H_AUTH" -d '{"title": "x"}')
check_code "PATCH /tasks/unknown" "$CODE" "404"
CODE=$(req -X DELETE "$BASE/tasks/does-not-exist" -H "$H_AUTH")
check_code "DELETE /tasks/unknown" "$CODE" "404"
CODE=$(req -X PATCH "$BASE/calendars/does-not-exist" -H "$H_JSON" -H "$H_AUTH" -d '{"name": "x"}')
check_code "PATCH /calendars/unknown" "$CODE" "404"
CODE=$(req -X DELETE "$BASE/calendars/does-not-exist" -H "$H_AUTH")
check_code "DELETE /calendars/unknown" "$CODE" "404"
CODE=$(req "$BASE/external-calendars/does-not-exist" -H "$H_AUTH")
check_code "GET /external-calendars/unknown" "$CODE" "404"
CODE=$(req -X DELETE "$BASE/external-calendars/does-not-exist" -H "$H_AUTH")
check_code "DELETE /external-calendars/unknown" "$CODE" "404"


step "N4. Negative - request body validation (422)"
info "Marshmallow / deserializer validation must reject bad enums, malformed dates, out-of-range numbers and bad URLs with a 4xx, not persist them."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Bad Status", "date_start": "2037-08-02T09:00:00Z", "date_end": "2037-08-02T10:00:00Z", "status": "not-a-status"}')
check_code "POST /events invalid status enum" "$CODE" "422"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Bad Date", "date_start": "not-a-date", "date_end": "2037-08-02T10:00:00Z"}')
check_code      "POST /events malformed date_start" "$CODE" "422"
check_error_code "POST /events malformed date_start error_code" "S000611"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/tasks" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Bad Priority", "priority": 42}')
check_code "POST /tasks priority out of range" "$CODE" "422"

CODE=$(req -X POST "$BASE/external-calendars" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Bad URL", "url": "not-a-url"}')
check_code "POST /external-calendars invalid url" "$CODE" "422"


step "N5. Negative + edge - attendance statuses (tentative / delegated / bad)"
info "Fresh invitation L1 -> L2 so LOGIN_2 is a real attendee; tentative and delegated are valid PARTSTAT values (200), an unknown status is rejected (422)."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Attendance Edge Invite\",
        \"date_start\": \"2037-08-03T13:00:00Z\",
        \"date_end\":   \"2037-08-03T14:00:00Z\",
        \"attendees\": [{\"email\": \"$LOGIN_2\", \"status\": \"needs-action\"}]
    }")
check_code "POST /events (attendance-edge invite)" "$CODE" "201"
ATT_UID=$(extract '.data.uid')
ATT_KEY_L1=$(extract '.data.key')

CODE=$(req "$BASE/events?start_date_time=2037-08-03T00:00:00Z&end_date_time=2037-08-03T23:59:59Z" -H "$H_AUTH_2")
check_code "GET /events (LOGIN_2) for attendance-edge date" "$CODE" "200"
ATT_KEY_L2=$(body | jq -r --arg uid "$ATT_UID" '[.data.events[] | select(.uid == $uid)][0].key // empty')
[ -n "$ATT_KEY_L2" ] && ok "LOGIN_2 sees the propagated invitation copy" || fail "LOGIN_2 copy not found - cannot test attendance"

CODE=$(req -X POST "$BASE/events/$ATT_KEY_L2/attendance" \
    -H "$H_JSON" -H "$H_AUTH_2" -d '{"status": "tentative", "sequence": 0}')
check_code "POST attendance tentative (LOGIN_2)" "$CODE" "200"

CODE=$(req -X POST "$BASE/events/$ATT_KEY_L2/attendance" \
    -H "$H_JSON" -H "$H_AUTH_2" -d '{"status": "delegated", "sequence": 0}')
check_code "POST attendance delegated (LOGIN_2)" "$CODE" "200"

CODE=$(req -X POST "$BASE/events/$ATT_KEY_L2/attendance" \
    -H "$H_JSON" -H "$H_AUTH_2" -d '{"status": "bogus", "sequence": 0}')
check_code "POST attendance invalid status -> 422" "$CODE" "422"

CODE=$(req -X POST "$BASE/events/$ATT_KEY_L2/attendance" \
    -H "$H_JSON" -H "$H_AUTH_2" -d '{"status": "accepted"}')
check_code "POST attendance without sequence -> 422" "$CODE" "422"

info "The organizer moves the slot, which bumps SEQUENCE. LOGIN_2 still holds the revision it was shown, so replaying it must be refused rather than accepting a slot never seen."
CODE=$(req -X PATCH "$BASE/events/$ATT_KEY_L1" -H "$H_JSON" -H "$H_AUTH" \
    -d '{"date_start": "2037-08-03T16:00:00Z", "date_end": "2037-08-03T17:00:00Z"}')
check_code "PATCH event (organizer moves the slot)" "$CODE" "200"

CODE=$(req -X POST "$BASE/events/$ATT_KEY_L2/attendance" \
    -H "$H_JSON" -H "$H_AUTH_2" -d '{"status": "accepted", "sequence": 0}')
check_code "POST attendance on an obsolete revision -> 409" "$CODE" "409"


step "N6. Inbound iMIP REPLY - provenance, single answer, revision"
info "Injects crafted METHOD:REPLY mails through the MTA and opens them as the organizer, which is what
  triggers inbound processing. Checks that a reply is only applied when it comes from the attendee it
  answers for, that echoing the guest list changes nothing but the sender, and that a reply carrying a
  superseded SEQUENCE is refused."

IMIP_R_NONCE=$(date +%s)
IMIP_R_START="20370810T130000Z"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"title\": \"Inbound Reply $IMIP_R_NONCE\",
        \"date_start\": \"2037-08-10T13:00:00Z\",
        \"date_end\":   \"2037-08-10T14:00:00Z\",
        \"attendees\": [
            {\"email\": \"$LOGIN_2\", \"status\": \"needs-action\"},
            {\"email\": \"$LOGIN_3\", \"status\": \"needs-action\"}
        ]
    }")
check_code "POST /events (inbound reply fixture)" "$CODE" "201"
IMIP_R_KEY=$(extract '.data.key')
IMIP_R_UID=$(extract '.data.uid')

partstat_of() {
    req "$BASE/events/$IMIP_R_KEY" -H "$H_AUTH" >/dev/null
    body | jq -r --arg m "$1" '[.data.attendees[] | select(.email == $m)][0].status // empty'
}

# 1. A third party answering for someone else must be refused.
SUBJ="Reply spoof $IMIP_R_NONCE"
send_imip_mail "$LOGIN_3" "$LOGIN_1" "$SUBJ" \
    "$(build_reply_ics "$IMIP_R_UID" 0 "$IMIP_R_START" "ATTENDEE;PARTSTAT=ACCEPTED:mailto:$LOGIN_2")"
if open_mail_by_subject "$H_AUTH" "$SUBJ" >/dev/null; then
    ok "organizer opened the spoofed reply"
    [ "$(partstat_of "$LOGIN_2")" = "needs-action" ] \
        && ok "reply from a third party did not change the attendee status" \
        || fail "reply from a third party changed the status to '$(partstat_of "$LOGIN_2")'"
else
    fail "spoofed reply never reached the organizer INBOX"
fi

# 2. Clients commonly echo the whole guest list; only the sender's own answer counts.
SUBJ="Reply echo $IMIP_R_NONCE"
send_imip_mail "$LOGIN_2" "$LOGIN_1" "$SUBJ" \
    "$(build_reply_ics "$IMIP_R_UID" 0 "$IMIP_R_START" \
        "ATTENDEE;PARTSTAT=ACCEPTED:mailto:$LOGIN_2\r\nATTENDEE;PARTSTAT=DECLINED:mailto:$LOGIN_3")"
if open_mail_by_subject "$H_AUTH" "$SUBJ" >/dev/null; then
    [ "$(partstat_of "$LOGIN_2")" = "accepted" ] \
        && ok "sender's own answer applied from an echoed guest list" \
        || fail "sender's answer not applied (got '$(partstat_of "$LOGIN_2")')"
    [ "$(partstat_of "$LOGIN_3")" = "needs-action" ] \
        && ok "the other echoed attendee was left untouched" \
        || fail "echoed attendee was modified (got '$(partstat_of "$LOGIN_3")')"
else
    fail "echoed reply never reached the organizer INBOX"
fi

# 3. Moving the slot bumps SEQUENCE and puts every attendee back to needs-action.
CODE=$(req -X PATCH "$BASE/events/$IMIP_R_KEY" -H "$H_JSON" -H "$H_AUTH" \
    -d '{"date_start": "2037-08-10T16:00:00Z", "date_end": "2037-08-10T17:00:00Z"}')
check_code "PATCH event (organizer moves the slot)" "$CODE" "200"
[ "$(partstat_of "$LOGIN_2")" = "needs-action" ] \
    && ok "moving the slot reset the attendee to needs-action" \
    || fail "attendee not reset after the move (got '$(partstat_of "$LOGIN_2")')"

# SEQUENCE:0 is what an omitted property means (RFC 5545 §3.8.7.4), so it is stale against the moved
# event - the guard cannot be sidestepped by leaving the property out.
SUBJ="Reply stale $IMIP_R_NONCE"
send_imip_mail "$LOGIN_2" "$LOGIN_1" "$SUBJ" \
    "$(build_reply_ics "$IMIP_R_UID" 0 "$IMIP_R_START" "ATTENDEE;PARTSTAT=ACCEPTED:mailto:$LOGIN_2")"
if open_mail_by_subject "$H_AUTH" "$SUBJ" >/dev/null; then
    [ "$(partstat_of "$LOGIN_2")" = "needs-action" ] \
        && ok "reply carrying a superseded revision was refused" \
        || fail "superseded reply was applied (got '$(partstat_of "$LOGIN_2")')"
else
    fail "stale reply never reached the organizer INBOX"
fi

# Same sender, same everything, but answering the revision actually stored: it must go through, so
# the guard is refusing staleness rather than blocking the path.
SUBJ="Reply current $IMIP_R_NONCE"
send_imip_mail "$LOGIN_2" "$LOGIN_1" "$SUBJ" \
    "$(build_reply_ics "$IMIP_R_UID" 1 "$IMIP_R_START" "ATTENDEE;PARTSTAT=ACCEPTED:mailto:$LOGIN_2")"
if open_mail_by_subject "$H_AUTH" "$SUBJ" >/dev/null; then
    [ "$(partstat_of "$LOGIN_2")" = "accepted" ] \
        && ok "reply answering the current revision was applied" \
        || fail "current-revision reply was dropped (got '$(partstat_of "$LOGIN_2")')"
else
    fail "current-revision reply never reached the organizer INBOX"
fi

# Reply ordering (RFC 5546 2.1.5): two answers to the same revision are separated by DTSTAMP only.
# The attendee declines at T+2h, then their earlier acceptance (T+1h) is delivered late: it must be
# discarded, not applied over the newer decline.
SUBJ="Reply newest $IMIP_R_NONCE"
send_imip_mail "$LOGIN_2" "$LOGIN_1" "$SUBJ" \
    "$(build_reply_ics "$IMIP_R_UID" 1 "$IMIP_R_START" \
        "ATTENDEE;PARTSTAT=DECLINED:mailto:$LOGIN_2" "20370810T150000Z")"
if open_mail_by_subject "$H_AUTH" "$SUBJ" >/dev/null; then
    [ "$(partstat_of "$LOGIN_2")" = "declined" ] \
        && ok "newer decline applied" \
        || fail "newer decline dropped (got '$(partstat_of "$LOGIN_2")')"
else
    fail "newest reply never reached the organizer INBOX"
fi

SUBJ="Reply outoforder $IMIP_R_NONCE"
send_imip_mail "$LOGIN_2" "$LOGIN_1" "$SUBJ" \
    "$(build_reply_ics "$IMIP_R_UID" 1 "$IMIP_R_START" \
        "ATTENDEE;PARTSTAT=ACCEPTED:mailto:$LOGIN_2" "20370810T140000Z")"
if open_mail_by_subject "$H_AUTH" "$SUBJ" >/dev/null; then
    [ "$(partstat_of "$LOGIN_2")" = "declined" ] \
        && ok "out-of-order earlier acceptance was discarded (DTSTAMP ordering)" \
        || fail "out-of-order reply was applied (got '$(partstat_of "$LOGIN_2")')"
else
    fail "out-of-order reply never reached the organizer INBOX"
fi


step "67. Delete - LOGIN_2 and LOGIN_3 freebusy events and calendars"
info "Removes the freebusy test events and calendars created by LOGIN_2 and LOGIN_3. Skipped without -d."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/events/$FB_L2_EVT" -H "$H_AUTH_2")
    check_code "DELETE /events/$FB_L2_EVT (L2 freebusy)" "$CODE" "200"
    CODE=$(req -X DELETE "$BASE/calendars/$CAL_KEY_2" -H "$H_AUTH_2")
    check_code "DELETE /calendars/$CAL_KEY_2 (LOGIN_2)" "$CODE" "200"

    CODE=$(req -X DELETE "$BASE/events/$FB_L3_EVT" -H "$H_AUTH_3")
    check_code "DELETE /events/$FB_L3_EVT (L3 freebusy)" "$CODE" "200"
    CODE=$(req -X DELETE "$BASE/calendars/$CAL_KEY_3" -H "$H_AUTH_3")
    check_code "DELETE /calendars/$CAL_KEY_3 (LOGIN_3)" "$CODE" "200"
else
    skip "DELETE LOGIN_2/LOGIN_3 freebusy events and calendars"
    info "L2: freebusy=$FB_L2_EVT  calendar=$CAL_KEY_2"
    info "L3: event=$FB_L3_EVT  calendar=$CAL_KEY_3"
fi


step "68. Calendar - delete (LOGIN_1 main calendar)"
info "Deletes the test calendar created in step 2. Verifies it returns 404 afterwards. Skipped without -d."

if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/calendars/$CAL_KEY" -H "$H_AUTH")
    check_code  "DELETE /calendars/$CAL_KEY" "$CODE" "200"
    check_error "DELETE /calendars/$CAL_KEY error_code"
    GONE=$(req "$BASE/calendars/$CAL_KEY" -H "$H_AUTH")
    [ "$GONE" = "404" ] && ok "deleted calendar no longer found (404)" || fail "deleted calendar still accessible (HTTP $GONE)"
else
    skip "DELETE calendar $CAL_KEY"
fi

# -- SUMMARY -------------------------------------------------------------------

echo ""
echo -e "${CYAN}==================================================${RESET}"
echo -e "  Results : ${GREEN}$PASS_COUNT passed${RESET}  ${RED}$FAIL_COUNT failed${RESET}"
if ! $DO_DELETE; then
    echo -e "  ${YELLOW}(run with -d to also execute delete operations)${RESET}"
fi
echo -e "${CYAN}==================================================${RESET}"
[ "$FAIL_COUNT" -eq 0 ] && exit 0 || exit 1

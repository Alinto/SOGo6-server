#!/usr/bin/env bash
# SOGo 6 Calendar API — functional test script
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
   7  RRULE expansion — GET with date range returns expanded occurrences
   8  Full-text search
   9  Detached occurrence lifecycle:
        a. POST occurrence with recurrence_id → separate DB row, parent_uid set
        b. GET /events returns the override in expansion (not the original slot)
        c. DELETE occurrence → slot cancelled via EXDATE, master survives
        d. GET /events no longer returns the cancelled slot
  10  EXDATE via PATCH (recurrence_exceptions added directly to master)
  11  Task CRUD (create, get, patch title / percent_complete, list)
  12  Isolation — tasks absent from GET /events, events absent from GET /tasks
  13  Cross-calendar — GET /events and GET /tasks without calendar key return
      data from all calendars and contain no leaked component type
  14  Error paths (unknown event key, unknown calendar key, override on
      non-recurring event)
  15  FreeBusy:
        a. Setup — LOGIN_2 (America/New_York) and LOGIN_3 (Asia/Tokyo) each create
           a calendar and an event; LOGIN_1 creates 2 events on 2026-06-15
        b. Multi-user JSON: LOGIN_3 queries LOGIN_1 + LOGIN_2 in one call
        c. Cross-user JSON query: LOGIN_3 → LOGIN_1 (2 busy periods)
        d. Common slot: LOGIN_3 → LOGIN_2, confirms LOGIN_2 busy at same 14:00 UTC
           slot as LOGIN_1 (scheduling conflict)
        e. No overlap: LOGIN_1 → LOGIN_3 during 14:00 window → 0 periods (free)
        f. Cross-tz: LOGIN_1 → LOGIN_3 at 22:00 UTC → BUSY (Asia/Tokyo event)
        g. Self-query: LOGIN_2 queries own free/busy
        h. Error — range > 90 days → S000614
  16  Conditional DELETE (only when -d is passed, steps 52–54)
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

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m';  RESET='\033[0m'

PASS_COUNT=0; FAIL_COUNT=0

ok()   { echo -e "${GREEN}  [PASS]${RESET} $1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "${RED}  [FAIL]${RESET} $1"; FAIL_COUNT=$((FAIL_COUNT+1)); }
step() {
    echo -e "\n${CYAN}━━ $1 ━━${RESET}"
    if $INTERACTIVE; then
        echo -e "${YELLOW}  Press SPACE to run this section, Q to quit...${RESET}"
        while IFS= read -r -s -n1 key; do
            if [[ "$key" == " " ]]; then break; fi
            if [[ "$key" == "q" || "$key" == "Q" ]]; then
                echo -e "\n${YELLOW}Interrupted.${RESET}"
                echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
                echo -e "  Results : ${GREEN}$PASS_COUNT passed${RESET}  ${RED}$FAIL_COUNT failed${RESET}"
                echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
                exit 0
            fi
        done
    fi
}
info() { echo -e "${YELLOW}  →${RESET} $1"; }
skip() { echo -e "${YELLOW}  [SKIP]${RESET} $1 (run with -d to execute)"; }

TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

req() {
    curl -s -o "$TMPFILE" -w "%{http_code}" "$@"
}
body()    { cat "$TMPFILE"; }
extract() { body | jq -r "${1} // empty"; }

check_code() {
    local label="$1" got="$2" want="$3"
    [ "$got" = "$want" ] && ok "$label (HTTP $got)" || fail "$label — expected HTTP $want, got $got"
}
check_error() {
    local label="$1"
    local code; code=$(body | jq -r '.error_code // empty')
    [ "$code" = "S000000" ] && ok "$label (S000000)" || fail "$label — error_code='$code'"
}
check_field() {
    local path="$1" want="$2"
    local got; got=$(body | jq -r "$path // empty")
    [ "$got" = "$want" ] && ok "$path = '$want'" || fail "$path — expected '$want', got '$got'"
}
check_not_empty() {
    local path="$1"
    local got; got=$(body | jq -r "$path // empty")
    [ -n "$got" ] && ok "$path is set ($got)" || fail "$path is empty"
}
check_count() {
    local label="$1" path="$2" want="$3"
    local got; got=$(body | jq -r "$path | length")
    [ "$got" = "$want" ] && ok "$label count=$want" || fail "$label — expected $want, got $got"
}

if ! command -v jq &>/dev/null; then
    echo "jq is required (brew install jq)"; exit 1
fi

echo ""
echo -e "${CYAN}SOGo 6 Calendar API — functional tests${RESET}"
echo -e "  Base URL : $BASE"
echo -e "  User     : $USER"
echo -e "  Deletes  : $(${DO_DELETE} && echo 'enabled (-d)' || echo 'disabled (omit -d to inspect DB)')"
echo -e "  Mode     : $(${INTERACTIVE} && echo 'interactive (-i)' || echo 'batch')"

# ── 1. LOGIN ──────────────────────────────────────────────────────────────────

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

# ── 2. CALENDAR CRUD ─────────────────────────────────────────────────────────

step "2. Calendar — create"
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

step "3. Calendar — list"
info "Verifies GET /calendars returns at least the newly created calendar (total_count >= 1)."

CODE=$(req "$BASE/calendars" -H "$H_AUTH")
check_code  "GET /calendars" "$CODE" "200"
check_error "GET /calendars error_code"
TOTAL=$(extract '.data.total_count')
info "Total calendars: $TOTAL"
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "total_count >= 1" || fail "total_count=$TOTAL"

step "4. Calendar — get by key"
info "Fetches the calendar by its key and verifies the name is returned correctly."

CODE=$(req "$BASE/calendars/$CAL_KEY" -H "$H_AUTH")
check_code  "GET /calendars/$CAL_KEY" "$CODE" "200"
check_field ".data.name" "Test Calendar"

step "5. Calendar — patch"
info "Renames the calendar and changes its color. Verifies both fields are updated in the response."

CODE=$(req -X PATCH "$BASE/calendars/$CAL_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Test Calendar (renamed)", "color": "#EF4444"}')
check_code  "PATCH /calendars/$CAL_KEY" "$CODE" "200"
check_field ".data.name"  "Test Calendar (renamed)"
check_field ".data.color" "#EF4444"

# ── 3. SIMPLE EVENT CRUD ─────────────────────────────────────────────────────

step "6. Event — create simple"
info "A regular timed event with categories. Verifies basic CRUD and field round-trip."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Team Meeting",
        "description": "Weekly sync",
        "location": "Room A",
        "date_start": "2026-06-10T09:00:00Z",
        "date_end":   "2026-06-10T10:00:00Z",
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

step "7. Event — get by key"
info "Fetches the event directly by its key. Verifies the title round-trips correctly."

CODE=$(req "$BASE/events/$EVT_KEY" -H "$H_AUTH")
check_code  "GET /events/$EVT_KEY" "$CODE" "200"
check_field ".data.title" "Team Meeting"

step "8. Event — patch title and location"
info "Partially updates an existing event. Only title and location are sent; other fields must be untouched."

CODE=$(req -X PATCH "$BASE/events/$EVT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Team Meeting (updated)", "location": "Room B"}')
check_code  "PATCH /events title+location" "$CODE" "200"
check_field ".data.title"    "Team Meeting (updated)"
check_field ".data.location" "Room B"

step "9. Event — patch categories"
info "Replaces the categories array on an existing event. Verifies the new array length is 3."

CODE=$(req -X PATCH "$BASE/events/$EVT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"categories": ["Work", "Meeting", "Q2"]}')
check_code "PATCH /events categories" "$CODE" "200"
check_count "categories" ".data.categories" "3"

# ── 4. ALL-DAY + COMPLEX EVENTS ──────────────────────────────────────────────

step "10. Event — create all-day"
info "An all-day event. Verifies that all_day=true is stored and returned correctly."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Company Holiday",
        "date_start": "2026-07-14T00:00:00Z",
        "date_end":   "2026-07-14T23:59:59Z",
        "all_day": true,
        "visibility": "public"
    }')
check_code  "POST /events all-day" "$CODE" "201"
check_field ".data.all_day" "true"
ALLDAY_KEY=$(extract '.data.key')

step "11. Event — create with attendees and reminders"
info "Event with organizer, two attendees (required/optional) and two reminders (popup/email)."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Project Kickoff",
        "location": "Conf Room B",
        "date_start": "2026-06-15T14:00:00Z",
        "date_end":   "2026-06-15T15:30:00Z",
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

# ── 5. RECURRING EVENTS ───────────────────────────────────────────────────────

step "12. Event — recurring daily (COUNT=5)"
info "Creates a VEVENT with RRULE:FREQ=DAILY;COUNT=5. Verifies the rule is stored correctly."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Daily Standup",
        "date_start": "2026-06-01T09:00:00Z",
        "date_end":   "2026-06-01T09:15:00Z",
        "timezone": "Europe/Paris",
        "recurrence_rule": {"frequency": "daily", "count": 5, "interval": 1}
    }')
check_code  "POST /events daily" "$CODE" "201"
check_error "POST /events daily error_code"
check_field ".data.recurrence_rule.frequency" "daily"
DAILY_KEY=$(extract '.data.key')
DAILY_UID=$(extract '.data.uid')
info "Daily event key: $DAILY_KEY  uid: $DAILY_UID"

step "13. Event — recurring weekly MO/WE/FR with UNTIL"
info "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=... Verifies by_day array length."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Cardio Session",
        "date_start": "2026-06-01T07:00:00Z",
        "date_end":   "2026-06-01T08:00:00Z",
        "timezone": "Europe/Paris",
        "recurrence_rule": {
            "frequency": "weekly",
            "interval": 1,
            "by_day": ["MO", "WE", "FR"],
            "until": "2026-07-31T23:59:59Z"
        }
    }')
check_code  "POST /events weekly MO/WE/FR" "$CODE" "201"
check_count "by_day" ".data.recurrence_rule.by_day" "3"
WEEKLY_KEY=$(extract '.data.key')

step "14. Event — recurring monthly BYMONTHDAY=1"
info "RRULE:FREQ=MONTHLY;BYMONTHDAY=1;COUNT=6"

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Monthly Review",
        "date_start": "2026-06-01T10:00:00Z",
        "date_end":   "2026-06-01T11:00:00Z",
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

# ── 6. RRULE EXPANSION ────────────────────────────────────────────────────────

step "15. RRULE expansion — daily event over its full range"
info "The daily event has COUNT=5 starting 2026-06-01. A GET over June 1-5 should expand it
  into 5 occurrences. We verify total_count >= 5 and that 'Daily Standup' appears 5 times."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-05T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events June 1-5 (daily expansion)" "$CODE" "200"
check_error "GET /events June 1-5 error_code"
TOTAL=$(extract '.data.total_count')
info "Events in June 1-5: $TOTAL"
[ "$TOTAL" -ge 5 ] 2>/dev/null && ok "total_count >= 5 (daily expansion)" || fail "total_count=$TOTAL (expected >= 5)"
FOUND=$(body | jq -r '[.data.events[] | select(.title == "Daily Standup")] | length')
[ "$FOUND" -ge 5 ] 2>/dev/null && ok "Daily Standup appears $FOUND times" || fail "Daily Standup appears $FOUND times (expected >= 5)"

step "16. RRULE expansion — weekly event over two months"
info "The weekly MO/WE/FR event runs from 2026-06-01 to 2026-07-31. June has ~13 occurrences.
  We verify >= 10 for the June window."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events June (weekly expansion)" "$CODE" "200"
FOUND=$(body | jq -r '[.data.events[] | select(.title == "Cardio Session")] | length')
info "Cardio Session occurrences in June: $FOUND"
[ "$FOUND" -ge 10 ] 2>/dev/null && ok "Cardio Session appears >= 10 times in June" || fail "Cardio Session appears $FOUND times (expected >= 10)"

step "17. RRULE expansion — monthly event UNTIL count boundary"
info "Monthly event starts 2026-06-01 with COUNT=6. July 1 is the second occurrence.
  We check that it appears in a July 1 query."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-07-01T00:00:00Z&end_date_time=2026-07-01T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events July 1 (monthly expansion)" "$CODE" "200"
FOUND=$(body | jq -r '[.data.events[] | select(.title == "Monthly Review")] | length')
[ "$FOUND" -ge 1 ] 2>/dev/null && ok "Monthly Review appears on July 1" || fail "Monthly Review does not appear on July 1 (found $FOUND)"

step "18. RRULE — patch recurrence rule (replace COUNT with UNTIL)"
info "Replaces the daily event RRULE to use an UNTIL date instead of COUNT."

CODE=$(req -X PATCH "$BASE/events/$DAILY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "recurrence_rule": {
            "frequency": "daily",
            "interval": 1,
            "until": "2026-06-15T23:59:59Z"
        }
    }')
check_code "PATCH /events recurrence_rule" "$CODE" "200"
UNTIL=$(extract '.data.recurrence_rule.until')
[ -n "$UNTIL" ] && ok "recurrence_rule.until set ($UNTIL)" || fail "recurrence_rule.until is empty"

# ── 7. DETACHED OCCURRENCE LIFECYCLE ─────────────────────────────────────────

step "19. Detached occurrence — create override for 2026-06-03"
info "POSTs a detached occurrence for the daily event: same uid, recurrence_id=2026-06-03T09:00:00Z.
  This represents 'move/edit only the June 3rd occurrence of Daily Standup'.
  The API stores this as a separate DB row linked to the master via parent_uid."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$DAILY_UID\",
        \"title\": \"Daily Standup (June 3 override)\",
        \"date_start\": \"2026-06-03T10:00:00Z\",
        \"date_end\":   \"2026-06-03T10:30:00Z\",
        \"timezone\": \"Europe/Paris\",
        \"recurrence_id\": \"2026-06-03T09:00:00Z\"
    }")
check_code  "POST /events detached occurrence" "$CODE" "201"
check_error "POST /events detached occurrence error_code"
check_field ".data.title" "Daily Standup (June 3 override)"
RECID=$(extract '.data.recurrence_id' | sed 's/\.000Z$/Z/')
[ "$RECID" = "2026-06-03T09:00:00Z" ] \
    && ok ".data.recurrence_id = '2026-06-03T09:00:00Z'" \
    || fail ".data.recurrence_id — expected '2026-06-03T09:00:00Z', got '$RECID'"
check_not_empty ".data.parent_uid"
OCCURRENCE_KEY=$(extract '.data.key')
OCCURRENCE_PARENT_UID=$(extract '.data.parent_uid')
info "Occurrence key: $OCCURRENCE_KEY"
info "parent_uid: $OCCURRENCE_PARENT_UID"
[ "$OCCURRENCE_PARENT_UID" = "$DAILY_UID" ] \
    && ok "parent_uid matches master uid" \
    || fail "parent_uid '$OCCURRENCE_PARENT_UID' does not match master uid '$DAILY_UID'"

step "20. Detached occurrence — GET expansion shows override, not original slot"
info "When expanding over June 3, the response must include the overridden occurrence
  (10:00-10:30, '...June 3 override') instead of the original 09:00 slot."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-06-03T00:00:00Z&end_date_time=2026-06-03T23:59:59Z" \
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

step "21. Detached occurrence — DELETE cancels the slot (EXDATE)"
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

    CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-06-03T00:00:00Z&end_date_time=2026-06-03T23:59:59Z" \
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

# ── 8. EXDATE VIA PATCH ───────────────────────────────────────────────────────

step "22. EXDATE via PATCH — cancel a specific date on the weekly event"
info "PATCHes the weekly MO/WE/FR event to add 2026-06-03T07:00:00Z to recurrence_exceptions.
  A subsequent GET for that slot must not return the weekly event."

CODE=$(req -X PATCH "$BASE/events/$WEEKLY_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"recurrence_exceptions": ["2026-06-03T07:00:00Z"]}')
check_code  "PATCH /events add recurrence_exceptions" "$CODE" "200"
EXDATES=$(extract '.data.recurrence_exceptions | length')
[ "$EXDATES" -ge 1 ] 2>/dev/null \
    && ok "recurrence_exceptions count >= 1 after patch ($EXDATES)" \
    || fail "recurrence_exceptions empty after patch"

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-06-03T07:00:00Z&end_date_time=2026-06-03T07:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events June 3 07:xx after EXDATE patch" "$CODE" "200"
CARDIO_COUNT=$(body | jq -r '[.data.events[] | select(.title == "Cardio Session")] | length')
[ "$CARDIO_COUNT" -eq 0 ] 2>/dev/null \
    && ok "Cardio Session absent for the EXDATEd slot" \
    || fail "Cardio Session still visible for EXDATEd slot (count=$CARDIO_COUNT)"

# ── 9. LIST AND SEARCH ────────────────────────────────────────────────────────

step "23. Events — list over June date range (no tasks)"
info "Only VEVENT components must appear; tasks created later must be absent."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code  "GET /events?start..end June" "$CODE" "200"
check_error "GET /events date range error_code"
TOTAL=$(extract '.data.total_count')
info "Events in June: $TOTAL"
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "total_count >= 1" || fail "total_count=$TOTAL"

step "24. Events — full-text search"
info "Searches events by title keyword 'Standup'. The daily recurring event must appear; at least 1 result expected."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?search=Standup" -H "$H_AUTH")
check_code  "GET /events?search=Standup" "$CODE" "200"
check_error "GET /events search error_code"
TOTAL=$(extract '.data.total_count')
info "Search 'Standup' → $TOTAL result(s)"
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "search returned >= 1 result" || fail "search returned $TOTAL results"

step "25. Events — no params (defaults to today)"
info "Without query params and no search, the API defaults to today's date range."

CODE=$(req "$BASE/calendars/$CAL_KEY/events" -H "$H_AUTH")
check_code  "GET /events (no params)" "$CODE" "200"
check_error "GET /events (no params) error_code"

# ── 10. TASK CRUD ─────────────────────────────────────────────────────────────

step "26. Task — create"
info "Creates a VTODO with a due date and percent_complete. Verifies component_type=task."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/tasks" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Write release notes",
        "description": "Document all changes for v1.0",
        "due": "2026-06-30T17:00:00Z",
        "percent_complete": 0,
        "categories": ["Dev", "Docs"]
    }')
check_code  "POST /tasks create" "$CODE" "201"
check_error "POST /tasks create error_code"
check_field ".data.title"          "Write release notes"
check_field ".data.component_type" "task"
TASK_KEY=$(extract '.data.key')
info "Task key: $TASK_KEY"

step "27. Task — get by key"
info "Fetches the task by its key. Verifies component_type=task and title round-trip."

CODE=$(req "$BASE/tasks/$TASK_KEY" -H "$H_AUTH")
check_code  "GET /tasks/$TASK_KEY" "$CODE" "200"
check_error "GET /tasks get error_code"
check_field ".data.title"          "Write release notes"
check_field ".data.component_type" "task"

step "28. Task — patch title and percent_complete"
info "Marks the task as 100% complete and renames it. Verifies both fields in the response."

CODE=$(req -X PATCH "$BASE/tasks/$TASK_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"title": "Write release notes (done)", "percent_complete": 100}')
check_code  "PATCH /tasks title+percent_complete" "$CODE" "200"
check_field ".data.title"            "Write release notes (done)"
check_field ".data.percent_complete" "100"

step "29. Task — create a second task for list/isolation checks"
info "Creates a second task so the list endpoint and isolation tests have at least 2 tasks to assert against."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/tasks" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Review PR #42",
        "due": "2026-06-20T12:00:00Z",
        "percent_complete": 50
    }')
check_code  "POST /tasks second task" "$CODE" "201"
TASK_KEY2=$(extract '.data.key')
info "Second task key: $TASK_KEY2"

step "30. Task — list (GET /calendars/{key}/tasks)"
info "Lists tasks for the calendar. Both tasks must appear; no events."

CODE=$(req "$BASE/calendars/$CAL_KEY/tasks?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-30T23:59:59Z" \
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

# ── 11. ISOLATION — tasks/events do not bleed across endpoints ────────────────

step "31. Isolation — tasks absent from GET /events"
info "The two tasks just created must not appear in the event list."

CODE=$(req "$BASE/calendars/$CAL_KEY/events?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /events (isolation check)" "$CODE" "200"
TASK_IN_EVENTS=$(body | jq -r '[.data.events[] | select(.component_type == "task")] | length')
[ "$TASK_IN_EVENTS" -eq 0 ] 2>/dev/null \
    && ok "no task found in GET /events (isolation OK)" \
    || fail "GET /events returned $TASK_IN_EVENTS task(s) — isolation broken"

step "32. Isolation — events absent from GET /tasks"
info "The events created earlier must not appear in the task list."

CODE=$(req "$BASE/calendars/$CAL_KEY/tasks?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-30T23:59:59Z" \
    -H "$H_AUTH")
check_code "GET /tasks (isolation check)" "$CODE" "200"
EVENT_IN_TASKS=$(body | jq -r '[.data.tasks[] | select(.component_type == "event" or .component_type == null)] | length')
[ "$EVENT_IN_TASKS" -eq 0 ] 2>/dev/null \
    && ok "no event found in GET /tasks (isolation OK)" \
    || fail "GET /tasks returned $EVENT_IN_TASKS event(s) — isolation broken"

# ── 12. CROSS-CALENDAR (no calendar key) ─────────────────────────────────────

step "33. GET /events — all calendars (no calendar key)"
info "GET /events without a calendar key must return events from all user calendars.
  The test calendar already has several events; the response must include at least one."

CODE=$(req "$BASE/events?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-30T23:59:59Z" \
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

step "34. GET /tasks — all calendars (no calendar key)"
info "GET /tasks without a calendar key must return tasks from all user calendars."

CODE=$(req "$BASE/tasks?start_date_time=2026-06-01T00:00:00Z&end_date_time=2026-06-30T23:59:59Z" \
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

# ── 13. ERROR PATHS ───────────────────────────────────────────────────────────

step "35. Error paths — unknown keys"
info "GET on a non-existent event key must return 404 + S000605. GET on a non-existent calendar key must return 404 + S000602."

CODE=$(req "$BASE/events/nonexistent-key-xyz" -H "$H_AUTH")
check_code "GET /events/nonexistent" "$CODE" "404"
ERR=$(extract '.error_code')
[ "$ERR" = "S000605" ] && ok "unknown event key → S000605" || fail "unknown event key → $ERR (expected S000605)"

CODE=$(req "$BASE/calendars/nonexistent-cal-xyz" -H "$H_AUTH")
check_code "GET /calendars/nonexistent" "$CODE" "404"
ERR=$(extract '.error_code')
[ "$ERR" = "S000602" ] && ok "unknown calendar key → S000602" || fail "unknown calendar key → $ERR (expected S000602)"

step "36. Error paths — detached occurrence on non-recurring event"
info "Posting a recurrence_id against a non-recurring event must be rejected (not 201)."

EVT_UID=$(curl -s "$BASE/events/$EVT_KEY" -H "$H_AUTH" | jq -r '.data.uid // empty')
CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"uid\": \"$EVT_UID\",
        \"title\": \"Bad override\",
        \"date_start\": \"2026-06-10T09:00:00Z\",
        \"date_end\":   \"2026-06-10T10:00:00Z\",
        \"recurrence_id\": \"2026-06-10T09:00:00Z\"
    }")
[ "$CODE" != "201" ] \
    && ok "non-recurring override rejected (HTTP $CODE)" \
    || fail "non-recurring override incorrectly accepted (HTTP 201)"

# ── 15. FREEBUSY ──────────────────────────────────────────────────────────────
#
# Timeline for 2026-06-15 (UTC):
#   LOGIN_1 (Europe/Paris)    : BUSY 09:00–10:00, BUSY 14:00–15:00
#   LOGIN_2 (America/New_York): BUSY 14:00–15:00           ← common slot with LOGIN_1
#   LOGIN_3 (Asia/Tokyo)      : BUSY 22:00–23:00           ← no overlap with LOGIN_1/LOGIN_2
#
# Tests:
#   - cross-user query (LOGIN_3 → LOGIN_1, LOGIN_3 → LOGIN_2)
#   - common busy slot confirmed on both sides
#   - slot where one is free while the other is busy
#   - self-query
#   - .ifb endpoint
#   - range-too-large error

step "37. FreeBusy setup — authenticate LOGIN_2 and LOGIN_3"
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

step "38. FreeBusy setup — LOGIN_1 adds 2 events on 2026-06-15 (Europe/Paris)"
info "09:00–10:00 UTC and 14:00–15:00 UTC. The 14:00 slot will be the common slot with LOGIN_2."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Morning (L1)",
        "date_start": "2026-06-15T09:00:00Z",
        "date_end":   "2026-06-15T10:00:00Z",
        "timezone": "Europe/Paris",
        "show_as": "busy"
    }')
check_code "POST /events FB Morning L1" "$CODE" "201"
FB_L1_MORNING=$(extract '.data.key')

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Afternoon (L1)",
        "date_start": "2026-06-15T14:00:00Z",
        "date_end":   "2026-06-15T15:00:00Z",
        "timezone": "Europe/Paris",
        "show_as": "busy"
    }')
check_code "POST /events FB Afternoon L1" "$CODE" "201"
FB_L1_AFTERNOON=$(extract '.data.key')

step "39. FreeBusy setup — LOGIN_2 creates calendar (America/New_York) + event at 14:00 UTC"
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
        "date_start": "2026-06-15T14:00:00Z",
        "date_end":   "2026-06-15T15:00:00Z",
        "timezone": "America/New_York",
        "show_as": "busy"
    }')
check_code "POST /events FB Standup L2" "$CODE" "201"
FB_L2_EVT=$(extract '.data.key')

step "40. FreeBusy setup — LOGIN_3 creates calendar (Asia/Tokyo) + event at 22:00 UTC"
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
        "date_start": "2026-06-15T22:00:00Z",
        "date_end":   "2026-06-15T23:00:00Z",
        "timezone": "Asia/Tokyo",
        "show_as": "busy"
    }')
check_code "POST /events FB Evening L3" "$CODE" "201"
FB_L3_EVT=$(extract '.data.key')

step "41. FreeBusy — multi-user JSON: LOGIN_3 queries LOGIN_1 + LOGIN_2 in one call"
info "Both attendees must appear in response. LOGIN_1 has 2 events, LOGIN_2 has 1."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\", \"$LOGIN_2\"],
        \"start\": \"2026-06-15T00:00:00Z\",
        \"end\":   \"2026-06-15T23:59:59Z\"
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

step "42. FreeBusy — cross-user JSON: LOGIN_3 queries LOGIN_1 on 2026-06-15"
info "LOGIN_1 has 2 events (09:00 and 14:00). Both must appear as BUSY."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2026-06-15T00:00:00Z\",
        \"end\":   \"2026-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy L3→L1 (JSON)" "$CODE" "200"
check_error "POST /freebusy L3→L1 error_code"
FB_L1_COUNT=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
info "LOGIN_1 busy periods on 2026-06-15: $FB_L1_COUNT"
[ "$FB_L1_COUNT" -ge 2 ] 2>/dev/null \
    && ok "LOGIN_1 has >= 2 busy periods (morning + afternoon)" \
    || fail "LOGIN_1 busy periods = $FB_L1_COUNT (expected >= 2)"
FB_L1_TYPES=$(body | jq -r --arg uid "$LOGIN_1" '[.data.attendees[$uid].periods[].type] | unique | .[]')
[ "$FB_L1_TYPES" = "busy" ] \
    && ok "all LOGIN_1 periods are type=busy" \
    || fail "unexpected period types for LOGIN_1: $FB_L1_TYPES"

step "43. FreeBusy — common slot: LOGIN_3 queries LOGIN_2 on 2026-06-15"
info "LOGIN_2 has the 14:00 event — same UTC slot as LOGIN_1's afternoon event."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_2\"],
        \"start\": \"2026-06-15T00:00:00Z\",
        \"end\":   \"2026-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy L3→L2 (JSON)" "$CODE" "200"
check_error "POST /freebusy L3→L2 error_code"
FB_L2_COUNT=$(body | jq -r --arg uid "$LOGIN_2" '.data.attendees[$uid].periods | length')
info "LOGIN_2 busy periods on 2026-06-15: $FB_L2_COUNT"
[ "$FB_L2_COUNT" -ge 1 ] 2>/dev/null \
    && ok "LOGIN_2 has >= 1 busy period" \
    || fail "LOGIN_2 busy periods = $FB_L2_COUNT (expected >= 1)"
FB_L2_SLOT=$(body | jq -r --arg uid "$LOGIN_2" '[.data.attendees[$uid].periods[] | select(.start == "20260615T140000Z")] | length')
[ "$FB_L2_SLOT" -ge 1 ] 2>/dev/null \
    && ok "LOGIN_2 is busy at 14:00 UTC (common slot with LOGIN_1 confirmed)" \
    || fail "LOGIN_2 is not busy at 14:00 UTC (expected common slot with LOGIN_1)"

step "44. FreeBusy — no overlap: LOGIN_1 queries LOGIN_3 on 14:00–15:00 UTC"
info "LOGIN_3 has no event at 14:00 UTC — must return 0 busy periods in that window."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_3\"],
        \"start\": \"2026-06-15T14:00:00Z\",
        \"end\":   \"2026-06-15T15:00:00Z\"
    }")
check_code  "POST /freebusy L1→L3 14:00 window" "$CODE" "200"
check_error "POST /freebusy L1→L3 14:00 error_code"
FB_L3_AT14=$(body | jq -r --arg uid "$LOGIN_3" '.data.attendees[$uid].periods | length')
[ "$FB_L3_AT14" -eq 0 ] 2>/dev/null \
    && ok "LOGIN_3 is free at 14:00 UTC — no overlap with LOGIN_1/LOGIN_2" \
    || fail "LOGIN_3 has $FB_L3_AT14 period(s) at 14:00 UTC (expected 0)"

step "45. FreeBusy — cross-tz: LOGIN_1 queries LOGIN_3 on 22:00–23:00 UTC"
info "LOGIN_3 has event at 22:00 UTC (Asia/Tokyo 07:00+9). Must appear BUSY."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_3\"],
        \"start\": \"2026-06-15T22:00:00Z\",
        \"end\":   \"2026-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy L1→L3 22:00 window" "$CODE" "200"
check_error "POST /freebusy L1→L3 22:00 error_code"
FB_L3_AT22=$(body | jq -r --arg uid "$LOGIN_3" '.data.attendees[$uid].periods | length')
[ "$FB_L3_AT22" -ge 1 ] 2>/dev/null \
    && ok "LOGIN_3 is busy at 22:00 UTC (cross-tz confirmed)" \
    || fail "LOGIN_3 has $FB_L3_AT22 period(s) at 22:00 UTC (expected >= 1)"

step "46. FreeBusy — self-query: LOGIN_2 queries own free/busy"
info "A user querying their own UID must see their own events. Verifies the server-side ownership check does not block self-access."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_2" \
    -d "{
        \"target_uids\": [\"$LOGIN_2\"],
        \"start\": \"2026-06-15T00:00:00Z\",
        \"end\":   \"2026-06-15T23:59:59Z\"
    }")
check_code  "POST /freebusy self (LOGIN_2)" "$CODE" "200"
check_error "POST /freebusy self error_code"
FB_SELF=$(body | jq -r --arg uid "$LOGIN_2" '.data.attendees[$uid].periods | length')
[ "$FB_SELF" -ge 1 ] 2>/dev/null \
    && ok "self freebusy returned >= 1 period" \
    || fail "self freebusy returned $FB_SELF periods (expected >= 1)"

step "47. FreeBusy — error: date range > 90 days → S000614"
info "Queries spanning more than 90 days must be rejected with HTTP 400 + S000614 to prevent expensive server-side scans."

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2026-01-01T00:00:00Z\",
        \"end\":   \"2026-12-31T23:59:59Z\"
    }")
check_code "POST /freebusy range too large" "$CODE" "400"
ERR=$(extract '.error_code')
[ "$ERR" = "S000614" ] \
    && ok "range too large → S000614" \
    || fail "range too large → $ERR (expected S000614)"

step "48. FreeBusy — show_as tentative → type tentative"
info "LOGIN_1 creates a TENTATIVE event on 2026-06-16 10:00–11:00 UTC."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Tentative (L1)",
        "date_start": "2026-06-16T10:00:00Z",
        "date_end":   "2026-06-16T11:00:00Z",
        "show_as": "tentative"
    }')
check_code "POST /events FB Tentative L1" "$CODE" "201"
FB_L1_TENTATIVE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2026-06-16T10:00:00Z\",
        \"end\":   \"2026-06-16T11:00:00Z\"
    }")
check_code  "POST /freebusy tentative window" "$CODE" "200"
FB_TENT_TYPE=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods[0].type')
[ "$FB_TENT_TYPE" = "tentative" ] \
    && ok "tentative event → type=tentative in freebusy" \
    || fail "tentative event → type=$FB_TENT_TYPE (expected tentative)"

step "49. FreeBusy — show_as free → excluded"
info "LOGIN_1 creates a FREE event on 2026-06-16 12:00–13:00 UTC. Must not appear in freebusy."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Free (L1)",
        "date_start": "2026-06-16T12:00:00Z",
        "date_end":   "2026-06-16T13:00:00Z",
        "show_as": "free"
    }')
check_code "POST /events FB Free L1" "$CODE" "201"
FB_L1_FREE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2026-06-16T12:00:00Z\",
        \"end\":   \"2026-06-16T13:00:00Z\"
    }")
check_code  "POST /freebusy free window" "$CODE" "200"
FB_FREE_COUNT=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
[ "$FB_FREE_COUNT" -eq 0 ] 2>/dev/null \
    && ok "show_as=free event excluded from freebusy" \
    || fail "show_as=free returned $FB_FREE_COUNT period(s) (expected 0)"

step "50. FreeBusy — status cancelled → excluded"
info "LOGIN_1 creates a CANCELLED event on 2026-06-16 14:00–15:00 UTC. Must not appear."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "FB Cancelled (L1)",
        "date_start": "2026-06-16T14:00:00Z",
        "date_end":   "2026-06-16T15:00:00Z",
        "show_as": "busy",
        "status": "cancelled"
    }')
check_code "POST /events FB Cancelled L1" "$CODE" "201"
FB_L1_CANCELLED=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2026-06-16T14:00:00Z\",
        \"end\":   \"2026-06-16T15:00:00Z\"
    }")
check_code  "POST /freebusy cancelled window" "$CODE" "200"
FB_CANC_COUNT=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods | length')
[ "$FB_CANC_COUNT" -eq 0 ] 2>/dev/null \
    && ok "status=cancelled event excluded from freebusy" \
    || fail "status=cancelled returned $FB_CANC_COUNT period(s) (expected 0)"

step "51. FreeBusy — title: public event exposes title, private event hides it"
info "PUBLIC event → title in response. PRIVATE event → no title key."

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Public Title Test",
        "date_start": "2026-06-16T08:00:00Z",
        "date_end":   "2026-06-16T09:00:00Z",
        "show_as": "busy",
        "visibility": "public"
    }')
check_code "POST /events FB Public Title L1" "$CODE" "201"
FB_L1_PUBLIC_TITLE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/calendars/$CAL_KEY/events" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "title": "Private Title Test",
        "date_start": "2026-06-16T09:00:00Z",
        "date_end":   "2026-06-16T10:00:00Z",
        "show_as": "busy",
        "visibility": "private"
    }')
check_code "POST /events FB Private Title L1" "$CODE" "201"
FB_L1_PRIVATE_TITLE=$(extract '.data.key')

CODE=$(req -X POST "$BASE/freebusy" \
    -H "$H_JSON" -H "$H_AUTH_3" \
    -d "{
        \"target_uids\": [\"$LOGIN_1\"],
        \"start\": \"2026-06-16T08:00:00Z\",
        \"end\":   \"2026-06-16T09:00:00Z\"
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
        \"start\": \"2026-06-16T09:00:00Z\",
        \"end\":   \"2026-06-16T10:00:00Z\"
    }")
check_code  "POST /freebusy private title window" "$CODE" "200"
FB_PRIV_HAS_TITLE=$(body | jq -r --arg uid "$LOGIN_1" '.data.attendees[$uid].periods[0] | has("title")')
[ "$FB_PRIV_HAS_TITLE" = "false" ] \
    && ok "PRIVATE event title hidden in freebusy" \
    || fail "PRIVATE event title key present in freebusy (expected absent)"

# ── 16. CONDITIONAL DELETES ───────────────────────────────────────────────────

step "52. Delete — LOGIN_1 freebusy events, tasks, and main test events"
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
    for key in "$TASK_KEY" "$TASK_KEY2"; do
        CODE=$(req -X DELETE "$BASE/tasks/$key" -H "$H_AUTH")
        check_code  "DELETE /tasks/$key" "$CODE" "200"
        check_error "DELETE /tasks/$key error_code"
        GONE=$(req "$BASE/tasks/$key" -H "$H_AUTH")
        [ "$GONE" = "404" ] && ok "$key gone after delete (404)" || fail "$key still accessible (HTTP $GONE)"
    done
else
    skip "DELETE LOGIN_1 events and tasks"
    info "Keys: EVT=$EVT_KEY  ALLDAY=$ALLDAY_KEY  COMPLEX=$COMPLEX_KEY"
    info "Keys: DAILY=$DAILY_KEY  WEEKLY=$WEEKLY_KEY  MONTHLY=$MONTHLY_KEY"
    info "Occurrence: $OCCURRENCE_KEY"
    info "Tasks: TASK=$TASK_KEY  TASK2=$TASK_KEY2"
    info "FreeBusy events L1: morning=$FB_L1_MORNING afternoon=$FB_L1_AFTERNOON"
    info "FreeBusy events L1: tentative=$FB_L1_TENTATIVE free=$FB_L1_FREE cancelled=$FB_L1_CANCELLED"
    info "FreeBusy events L1: public_title=$FB_L1_PUBLIC_TITLE private_title=$FB_L1_PRIVATE_TITLE"
fi

step "53. Delete — LOGIN_2 and LOGIN_3 freebusy events and calendars"
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
    info "L2: event=$FB_L2_EVT  calendar=$CAL_KEY_2"
    info "L3: event=$FB_L3_EVT  calendar=$CAL_KEY_3"
fi

step "54. Calendar — delete (LOGIN_1 main calendar)"
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

# ── SUMMARY ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  Results : ${GREEN}$PASS_COUNT passed${RESET}  ${RED}$FAIL_COUNT failed${RESET}"
if ! $DO_DELETE; then
    echo -e "  ${YELLOW}(run with -d to also execute delete operations)${RESET}"
fi
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
[ "$FAIL_COUNT" -eq 0 ] && exit 0 || exit 1

#!/usr/bin/env bash
# SOGo 6 Contact API - functional test script
#
# Usage:
#   ./test_api_contact.sh [OPTIONS] [base_url] [username] [password]
#
# Defaults: http://localhost:5000/api/user/v1   sogo-tests1@example.org   sogo

set -euo pipefail

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [base_url] [username] [password]

Functional smoke tests for the SOGo 6 Contact REST API.

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

TEST COVERAGE:
   1  Authentication (login, token extraction)
   2  Address book CRUD (create, list, get, patch)
   3  Contact CRUD with sub-objects (create, flat get, field round-trip)
   4  Contact PATCH (partial update preserves other fields)
   5  Full-text search
   6  Pagination (page/page_size + X-Pagination header)
   7  Sorting (sort_by + sort_order)
   8  Cross-book listing (GET /contacts spans all books)
   9  Error paths (unknown contact key, unknown address book)
  10  Recipient autocomplete (/contacts/autocomplete)
  11  Distribution lists (create, list, get, patch, error path)
  12  Conditional DELETE (only with -d): list, contact, then address book
EOF
    exit 0
}

DEFAULT_BASE_URL="http://localhost:5000/api/user/v1"
DEFAULT_LOGIN="sogo-tests1@example.org"
DEFAULT_PASSWORD="sogo"

DO_DELETE=false
INTERACTIVE=false

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
    echo -e "\n${CYAN}== $1 ==${RESET}"
    if $INTERACTIVE; then
        echo -e "${YELLOW}  Press SPACE to run this section, Q to quit...${RESET}"
        while IFS= read -r -s -n1 key; do
            if [[ "$key" == " " ]]; then break; fi
            if [[ "$key" == "q" || "$key" == "Q" ]]; then
                echo -e "\n${YELLOW}Interrupted.${RESET}"
                echo -e "  Results : ${GREEN}$PASS_COUNT passed${RESET}  ${RED}$FAIL_COUNT failed${RESET}"
                exit 0
            fi
        done
    fi
}
info() { echo -e "${YELLOW}  ->${RESET} $1"; }
skip() { echo -e "${YELLOW}  [SKIP]${RESET} $1 (run with -d to execute)"; }

TMPFILE=$(mktemp)
HDRFILE=$(mktemp)
trap 'rm -f "$TMPFILE" "$HDRFILE"' EXIT

req() {
    curl -s -D "$HDRFILE" -o "$TMPFILE" -w "%{http_code}" "$@"
}
body()    { cat "$TMPFILE"; }
extract() { body | jq -r "${1} // empty"; }

# Parse the X-Pagination response header (JSON) and return one of its fields.
pagination() {
    grep -i '^x-pagination:' "$HDRFILE" | head -1 \
        | sed -E 's/^[Xx]-[Pp]agination:[[:space:]]*//; s/\r$//' \
        | jq -r "${1} // empty"
}

check_code() {
    local label="$1" got="$2" want="$3"
    [ "$got" = "$want" ] && ok "$label (HTTP $got)" || fail "$label - expected HTTP $want, got $got"
}
check_error() {
    local label="$1"
    local code; code=$(body | jq -r '.error_code // empty')
    [ "$code" = "S000000" ] && ok "$label (S000000)" || fail "$label - error_code='$code'"
}
check_error_code() {
    local label="$1" want="$2"
    local code; code=$(body | jq -r '.error_code // empty')
    [ "$code" = "$want" ] && ok "$label ($want)" || fail "$label - expected '$want', got '$code'"
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

if ! command -v jq &>/dev/null; then
    echo "jq is required (brew install jq)"; exit 1
fi

echo ""
echo -e "${CYAN}SOGo 6 Contact API - functional tests${RESET}"
echo -e "  Base URL : $BASE"
echo -e "  User     : $USER"
echo -e "  Deletes  : $(${DO_DELETE} && echo 'enabled (-d)' || echo 'disabled (omit -d to inspect DB)')"
echo -e "  Mode     : $(${INTERACTIVE} && echo 'interactive (-i)' || echo 'batch')"

# 1. LOGIN
step "1. Authentication"
info "Logs in and extracts the JWT token used by all subsequent requests."

CODE=$(req -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}")
check_code "POST /auth/login" "$CODE" "200"

TOKEN=$(extract '.data.jwt_token')
if [ -z "$TOKEN" ]; then
    fail "Could not extract auth token"; echo "Response: $(body)"; exit 1
fi
ok "Token obtained"

H_AUTH="Authorization: Bearer $TOKEN"
H_JSON="Content-Type: application/json"

# 2. ADDRESS BOOK CRUD
step "2. Address book - create"
info "Creates a fresh address book that will hold all contacts created during this run."

CODE=$(req -X POST "$BASE/addressbooks" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Test Book", "description": "Created by functional test script"}')
check_code  "POST /addressbooks" "$CODE" "201"
check_error "POST /addressbooks error_code"
check_field ".data.name" "Test Book"
AB_KEY=$(extract '.data.key')
info "Address book key: $AB_KEY"

step "3. Address book - list"
CODE=$(req "$BASE/addressbooks" -H "$H_AUTH")
check_code  "GET /addressbooks" "$CODE" "200"
TOTAL=$(extract '.data.total_count')
info "Total address books: $TOTAL"
[ "$TOTAL" -ge 1 ] 2>/dev/null && ok "total_count >= 1" || fail "total_count=$TOTAL"

step "4. Address book - get + patch"
CODE=$(req "$BASE/addressbooks/$AB_KEY" -H "$H_AUTH")
check_code  "GET /addressbooks/$AB_KEY" "$CODE" "200"
check_field ".data.name" "Test Book"

CODE=$(req -X PATCH "$BASE/addressbooks/$AB_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"name": "Test Book (renamed)"}')
check_code  "PATCH /addressbooks/$AB_KEY" "$CODE" "200"
check_field ".data.name" "Test Book (renamed)"

# 3. CONTACT CRUD
step "5. Contact - create with sub-objects"
info "Creates a contact with emails, phones, addresses and a birthday. Verifies field round-trip."

CODE=$(req -X POST "$BASE/addressbooks/$AB_KEY/contacts" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{
        "display_name": "John Doe",
        "first_name": "John",
        "last_name": "Doe",
        "organization": "Acme Corp",
        "job_title": "Engineer",
        "emails": [{"value": "john@acme.com", "types": ["work"], "pref": 1}],
        "phones": [{"number": "+33123456789", "types": ["cell"]}],
        "addresses": [{"street": "1 rue de Paris", "locality": "Paris", "postal_code": "75001", "country": "France", "types": ["home"]}],
        "categories": ["colleague"],
        "birthday": "1990-04-15"
    }')
check_code  "POST /addressbooks/$AB_KEY/contacts" "$CODE" "201"
check_error "POST contacts error_code"
check_field ".data.display_name" "John Doe"
check_field ".data.emails[0].value" "john@acme.com"
check_field ".data.phones[0].number" "+33123456789"
check_field ".data.addresses[0].locality" "Paris"
check_field ".data.birthday" "1990-04-15"
check_not_empty ".data.uid"
CT_KEY=$(extract '.data.key')
info "Contact key: $CT_KEY"

step "6. Contact - get by key (nested under address book)"
info "Fetches the contact via /addressbooks/<key>/contacts/<key>."
CODE=$(req "$BASE/addressbooks/$AB_KEY/contacts/$CT_KEY" -H "$H_AUTH")
check_code  "GET /addressbooks/$AB_KEY/contacts/$CT_KEY" "$CODE" "200"
check_field ".data.display_name" "John Doe"
check_field ".data.organization" "Acme Corp"

# 4. CONTACT PATCH
step "7. Contact - patch (partial)"
info "Patches the note only; verifies the display name is preserved."
CODE=$(req -X PATCH "$BASE/addressbooks/$AB_KEY/contacts/$CT_KEY" \
    -H "$H_JSON" -H "$H_AUTH" \
    -d '{"note": "Met at conference"}')
check_code  "PATCH /addressbooks/$AB_KEY/contacts/$CT_KEY" "$CODE" "200"
check_field ".data.note" "Met at conference"
check_field ".data.display_name" "John Doe"
# A partial PATCH must not wipe fields it did not touch (regression: schema load_default).
check_field ".data.emails[0].value" "john@acme.com"
check_field ".data.phones[0].number" "+33123456789"

# Seed a few more contacts for search / pagination / sort
info "Seeding additional contacts (Alice Martin, Bob Acme, Zoe Last)."
for c in \
    '{"display_name":"Alice Martin","last_name":"Martin","organization":"Globex","emails":[{"value":"alice@globex.com"}]}' \
    '{"display_name":"Bob Acme","last_name":"Acme","organization":"Acme Corp"}' \
    '{"display_name":"Zoe Last","last_name":"Zzz"}' ; do
    req -X POST "$BASE/addressbooks/$AB_KEY/contacts" -H "$H_JSON" -H "$H_AUTH" -d "$c" >/dev/null
done

# 5. SEARCH
step "8. Contact - full-text search"
info "Searches for 'acme'; expects at least the two Acme Corp contacts."
CODE=$(req "$BASE/addressbooks/$AB_KEY/contacts?search=acme" -H "$H_AUTH")
check_code "GET contacts?search=acme" "$CODE" "200"
FOUND=$(extract '.data.contacts | length')
info "Matches: $FOUND"
[ "$FOUND" -ge 2 ] 2>/dev/null && ok "search returned >= 2" || fail "search returned $FOUND"

# 6. PAGINATION
step "9. Contact - pagination (page_size=2)"
info "Requests the first page of size 2; checks the body holds 2 contacts and X-Pagination.total counts all."
CODE=$(req "$BASE/addressbooks/$AB_KEY/contacts?page=1&page_size=2" -H "$H_AUTH")
check_code  "GET contacts?page=1&page_size=2" "$CODE" "200"
check_count "page body" ".data.contacts" "2"
PTOTAL=$(pagination '.total')
info "X-Pagination total: $PTOTAL"
[ "$PTOTAL" -ge 4 ] 2>/dev/null && ok "X-Pagination total >= 4" || fail "X-Pagination total=$PTOTAL"

# 7. SORT
step "10. Contact - sort by last_name desc"
info "Sorts descending by last_name; expects 'Zzz' (Zoe Last) first."
CODE=$(req "$BASE/addressbooks/$AB_KEY/contacts?sort_by=last_name&sort_order=desc&page_size=20" -H "$H_AUTH")
check_code "GET contacts?sort_by=last_name&sort_order=desc" "$CODE" "200"
FIRST=$(extract '.data.contacts[0].last_name')
info "First last_name: $FIRST"
[ "$FIRST" = "Zzz" ] && ok "desc sort puts Zzz first" || fail "expected Zzz first, got '$FIRST'"

# 8. CROSS-BOOK LISTING
step "11. Contact - cross-book listing (GET /contacts)"
info "Lists contacts across every address book; total should cover all seeded contacts."
CODE=$(req "$BASE/contacts?page_size=50" -H "$H_AUTH")
check_code "GET /contacts" "$CODE" "200"
ALL=$(extract '.data.contacts | length')
info "Contacts across all books: $ALL"
[ "$ALL" -ge 4 ] 2>/dev/null && ok "cross-book listing >= 4" || fail "cross-book listing=$ALL"

# 9. ERROR PATHS
step "12. Error paths"
info "Unknown contact key -> 404 S000703; unknown address book -> 404 S000701."
CODE=$(req "$BASE/addressbooks/$AB_KEY/contacts/does-not-exist" -H "$H_AUTH")
check_code       "GET /addressbooks/$AB_KEY/contacts/does-not-exist" "$CODE" "404"
check_error_code "unknown contact error_code" "S000703"

CODE=$(req "$BASE/addressbooks/does-not-exist" -H "$H_AUTH")
check_code       "GET /addressbooks/does-not-exist" "$CODE" "404"
check_error_code "unknown address book error_code" "S000701"

# 10. AUTOCOMPLETE
step "13. Contact - recipient autocomplete"
info "Self-contained: a probe contact is created just before each query (robust to a clean DB)."
req -X POST "$BASE/addressbooks/$AB_KEY/contacts" -H "$H_JSON" -H "$H_AUTH" \
    -d '{"display_name":"Zorglub Probe","emails":[{"value":"zorglub@probe.test"}]}' >/dev/null
CODE=$(req "$BASE/contacts/autocomplete?q=zorglub" -H "$H_AUTH")
check_code "GET /contacts/autocomplete?q=zorglub" "$CODE" "200"
SUGG=$(extract '.data.suggestions | length')
info "Suggestions: $SUGG"
[ "$SUGG" -ge 1 ] 2>/dev/null && ok "autocomplete returned >= 1 suggestion" || fail "autocomplete returned $SUGG"
check_not_empty ".data.suggestions[0].email"
check_not_empty ".data.suggestions[0].contact_key"
check_not_empty ".data.suggestions[0].address_book.key"
check_not_empty ".data.suggestions[0].address_book.name"

CODE=$(req "$BASE/contacts/autocomplete?q=a" -H "$H_AUTH")
check_code "GET /contacts/autocomplete?q=a (below min length)" "$CODE" "200"
SUGG=$(extract '.data.suggestions | length')
[ "$SUGG" = "0" ] && ok "too-short query returns 0 suggestions" || fail "expected 0, got $SUGG"

info "Interior email segment must be searchable (Postgres lexes a whole email as one token)."
req -X POST "$BASE/addressbooks/$AB_KEY/contacts" -H "$H_JSON" -H "$H_AUTH" \
    -d '{"display_name":"Marie Curie","emails":[{"value":"marie.curie77@lab.test"}]}' >/dev/null
CODE=$(req "$BASE/contacts/autocomplete?q=curie77" -H "$H_AUTH")
check_code "GET /contacts/autocomplete?q=curie77 (interior email segment)" "$CODE" "200"
SUGG=$(extract '.data.suggestions | length')
[ "$SUGG" -ge 1 ] 2>/dev/null && ok "interior email segment matches" || fail "interior segment returned $SUGG"

# 11. DISTRIBUTION LISTS
step "14. Distribution list - create"
info "Creates a probe member, then a list referencing two contacts; checks member_count round-trip."
req -X POST "$BASE/addressbooks/$AB_KEY/contacts" -H "$H_JSON" -H "$H_AUTH" \
    -d '{"display_name":"List Member Two","emails":[{"value":"member2@list.test"}]}' >/dev/null
LM2=$(extract '.data.key')

CODE=$(req -X POST "$BASE/addressbooks/$AB_KEY/lists" -H "$H_JSON" -H "$H_AUTH" \
    -d "{\"name\":\"Project Team\",\"description\":\"Functional test list\",\"members\":[\"$CT_KEY\",\"$LM2\"]}")
check_code  "POST /addressbooks/$AB_KEY/lists" "$CODE" "201"
check_error "POST lists error_code"
check_field ".data.name" "Project Team"
check_field ".data.member_count" "2"
check_not_empty ".data.key"
LIST_KEY=$(extract '.data.key')
info "List key: $LIST_KEY"

step "15. Distribution list - collection + get by key"
CODE=$(req "$BASE/addressbooks/$AB_KEY/lists" -H "$H_AUTH")
check_code "GET /addressbooks/$AB_KEY/lists" "$CODE" "200"
LCOUNT=$(extract '.data.lists | length')
info "Lists in book: $LCOUNT"
[ "$LCOUNT" -ge 1 ] 2>/dev/null && ok "list collection >= 1" || fail "list collection=$LCOUNT"

CODE=$(req "$BASE/addressbooks/$AB_KEY/lists/$LIST_KEY" -H "$H_AUTH")
check_code  "GET /addressbooks/$AB_KEY/lists/$LIST_KEY" "$CODE" "200"
check_field ".data.member_count" "2"
check_count "members" ".data.members" "2"

info "A distribution list must surface in autocomplete with type=list, member_count and resolved members."
info "Assertions target this run's list ($LIST_KEY): autocomplete is transverse and may match other lists."
CODE=$(req "$BASE/contacts/autocomplete?q=Project" -H "$H_AUTH")
check_code "GET /contacts/autocomplete?q=Project" "$CODE" "200"
LSUG=$(body | jq -r --arg k "$LIST_KEY" '.data.suggestions[] | select(.type=="list" and .list_key==$k) | .member_count')
[ "$LSUG" = "2" ] && ok "list suggestion has member_count=2" || fail "list suggestion member_count='$LSUG'"
LMEM=$(body | jq -r --arg k "$LIST_KEY" '.data.suggestions[] | select(.type=="list" and .list_key==$k) | .members[0].email // empty')
[ -n "$LMEM" ] && ok "list members are resolved with an email ($LMEM)" || fail "list members not resolved"

step "16. Distribution list - patch (rename + membership replacement)"
info "Renames the list and reduces its membership to a single contact."
CODE=$(req -X PATCH "$BASE/addressbooks/$AB_KEY/lists/$LIST_KEY" -H "$H_JSON" -H "$H_AUTH" \
    -d "{\"name\":\"Core Team\",\"members\":[\"$CT_KEY\"]}")
check_code  "PATCH /addressbooks/$AB_KEY/lists/$LIST_KEY" "$CODE" "200"
check_field ".data.name" "Core Team"
check_field ".data.member_count" "1"

step "17. Distribution list - error path"
info "Unknown list key -> 404 S000710."
CODE=$(req "$BASE/addressbooks/$AB_KEY/lists/does-not-exist" -H "$H_AUTH")
check_code       "GET /addressbooks/$AB_KEY/lists/does-not-exist" "$CODE" "404"
check_error_code "unknown list error_code" "S000710"

# 12. CONDITIONAL DELETE
step "18. Cleanup (DELETE)"
if $DO_DELETE; then
    CODE=$(req -X DELETE "$BASE/addressbooks/$AB_KEY/lists/$LIST_KEY" -H "$H_AUTH")
    check_code "DELETE /addressbooks/$AB_KEY/lists/$LIST_KEY" "$CODE" "200"
    CODE=$(req "$BASE/addressbooks/$AB_KEY/lists/$LIST_KEY" -H "$H_AUTH")
    check_code "GET deleted list -> 404" "$CODE" "404"
    CODE=$(req -X DELETE "$BASE/addressbooks/$AB_KEY/contacts/$CT_KEY" -H "$H_AUTH")
    check_code "DELETE /addressbooks/$AB_KEY/contacts/$CT_KEY" "$CODE" "200"
    CODE=$(req "$BASE/addressbooks/$AB_KEY/contacts/$CT_KEY" -H "$H_AUTH")
    check_code "GET deleted contact -> 404" "$CODE" "404"
    CODE=$(req -X DELETE "$BASE/addressbooks/$AB_KEY" -H "$H_AUTH")
    check_code "DELETE /addressbooks/$AB_KEY" "$CODE" "200"
else
    skip "DELETE list/$LIST_KEY, contact/$CT_KEY and address book/$AB_KEY"
fi

echo ""
echo -e "${CYAN}=================================================${RESET}"
echo -e "  Results : ${GREEN}$PASS_COUNT passed${RESET}  ${RED}$FAIL_COUNT failed${RESET}"
echo -e "${CYAN}=================================================${RESET}"
[ "$FAIL_COUNT" -eq 0 ]

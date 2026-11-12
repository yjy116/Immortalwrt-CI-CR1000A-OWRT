#!/bin/bash
set -eu
HONK_DIR=${1:?pass the prepared openwrt-honk directory}
TEST_DIR=$(mktemp -d)
EFFECTS=$TEST_DIR/effects
ERRORS=$TEST_DIR/errors
trap 'command rm -f "$EFFECTS" "$ERRORS"; rmdir "$TEST_DIR"' EXIT

# Replace process/network probes and writes, not the production reclaim logic.
timeout() { return 1; }
pidof() {
  if [ "$1" = "${FAILED_PROBE:-none}" ]; then return "$PROBE_STATUS"; fi
  [ "$1" = "$PEER" ] || return 1
  printf '4243\n'
}

ip() {
  case "$*" in
    'netns list')
      [ "${NS_LIST_ERROR:-0}" = 0 ] || return 2
      [ "$NETNS" = 0 ] || printf 'daens\n'
      return 0 ;;
    'netns pids daens')
      [ "${NS_PID_ERROR:-0}" = 0 ] || return 2
      [ "$PEER" = none ] || printf '4243\n'
      return 0 ;;
    'link show dae0'|'link show dae0peer') [ "$LINK" = 1 ] ;;
    'link del dae0'|'link del dae0peer') LINK=0; printf 'delete-link\n' >> "$EFFECTS" ;;
    'netns del daens') NETNS=0; printf 'delete-netns\n' >> "$EFFECTS" ;;
    *) echo "unexpected ip call: $*" >&2; return 99 ;;
  esac
}

configure_probe_fault() {
  case "$1" in
    none) ;;
    missing-probe) FAILED_PROBE=dae; PROBE_STATUS=127 ;;
    invalid-probe) FAILED_PROBE=daed; PROBE_STATUS=2 ;;
    core-probe-error) FAILED_PROBE=honk-core; PROBE_STATUS=2 ;;
    namespace-list-error) NS_LIST_ERROR=1 ;;
    namespace-pids-error) NS_PID_ERROR=1 ;;
    *) echo "unknown test scenario: $1" >&2; return 99 ;;
  esac
}

check_reclaim() (
  PEER=$2 LINK=1 NETNS=1 FAILED_PROBE=none PROBE_STATUS=1
  NS_LIST_ERROR=0 NS_PID_ERROR=0
  : > "$EFFECTS"
  : > "$ERRORS"
  configure_probe_fault "$3"
  source "$HONK_DIR/honk/files/lifecycle.sh"
  result=0
  honk_lifecycle_reclaim_resources 2> "$ERRORS" || result=$?
  if [ "$1" = clean ]; then
    [ "$result" = 0 ] && grep -qx delete-link "$EFFECTS" &&
      grep -qx delete-netns "$EFFECTS"
    return $?
  fi
  [ "$result" -ne 0 ] || { echo 'reclaim incorrectly succeeded'; return 1; }
  [ ! -s "$EFFECTS" ] || { cat "$EFFECTS"; return 1; }
  [ -s "$ERRORS" ] || { echo 'missing explicit refusal diagnostic'; return 1; }
)

failed=0
while read -r scenario peer fault; do
  if check_reclaim "$scenario" "$peer" "$fault"; then
    printf 'PASS reclaim %s\n' "$scenario"
  else
    printf 'FAIL reclaim %s\n' "$scenario"
    failed=$((failed + 1))
  fi
done <<'CASES'
clean none none
dae dae none
daed daed none
honk-core honk-core none
unknown-owner unknown-owner none
missing-probe none missing-probe
invalid-probe none invalid-probe
core-probe-error none core-probe-error
namespace-list-error none namespace-list-error
namespace-pids-error none namespace-pids-error
CASES
[ "$failed" = 0 ]

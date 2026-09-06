#!/usr/bin/env bash

# Fetch pre-archived daily global 'oper' forcing GRIB tarballs from ECFS,
# instead of a fresh MARS retrieval through ecland-portal.
#
# ../ecland-portal's create_forcing tool retrieves this exact same class/
# stream/expver from MARS on demand (see its forcing_config.yaml,
# forcingCommonName: forcing_od_1_oper_1), at roughly 1 hour of wall clock per
# month spanned. ECFS already holds one tar.gz per calendar day at
# /paga/OSM_FORCING/forcing_od_1_oper_1_<YYYYMMDD>.tar.gz -- global GRIB, not
# yet extracted to any point -- going back to at least 2016. Pulling those
# with ecp instead skips MARS entirely.
#
# NOTE: despite the *_1_oper_1 common name matching create_forcing's own
# forcing-cache convention (<forcingCommonName>_<YYYYMM00>.tar.gz, see its
# README and config/defaults.yaml's save_forcing_grib), these ECFS archives
# are DAILY, not monthly, and are not (yet) wired into that cache mechanism --
# this script just stages the raw tarballs under forcing/raw/. Turning them
# into ecLand-ready forcing (point extraction + metview processing) is a
# separate, not-yet-written step.
#
# Size: ~2.1 GB/day in 2017-2023 (was ~0.68 GB/day in 2016 -- a resolution
# change). A 2017-01-01..2023-01-01 pull is 2192 days, ~4.5 TB.
#
# Safe to re-run: ecp's default -n behaviour skips a destination file that
# already exists, so an interrupted run resumes rather than re-copying.
#
# Usage:
#   get_forcing_ecfs.sh START_DATE END_DATE [DEST_DIR] [CONCURRENCY]
#
#     START_DATE, END_DATE  YYYYMMDD, inclusive
#     DEST_DIR              default: $SCRATCH/ifs-lakebench/forcing/raw
#     CONCURRENCY           parallel ecp transfers, default 4 -- ECFS is
#                           backed by a tape robot; keep this modest rather
#                           than hammering it.
#
# (C) Copyright 2026- ECMWF. Apache Licence Version 2.0.

set -euo pipefail

usage() {
  awk '/^# Usage:/{p=1} /^# \(C\) Copyright/{p=0} p' "${BASH_SOURCE[0]}" \
    | sed 's/^#[[:space:]]\{0,1\}//'
}

if [[ $# -lt 2 ]]; then
  usage >&2
  exit 2
fi

START_DATE="$1"
END_DATE="$2"
DEST_DIR="${3:-${SCRATCH:?SCRATCH not set}/ifs-lakebench/forcing/raw}"
CONCURRENCY="${4:-4}"
ECFS_DIR="ec:/paga/OSM_FORCING"
PREFIX="forcing_od_1_oper_1"

for d in "${START_DATE}" "${END_DATE}"; do
  [[ "${d}" =~ ^[0-9]{8}$ ]] || { echo "ERROR: date must be YYYYMMDD, got '${d}'" >&2; exit 2; }
done

mkdir -p "${DEST_DIR}"

# Build the day list with Python rather than `date -d` looping in a subshell
# per day: identical result, one process instead of thousands.
DAY_LIST="$(
  python3 - "${START_DATE}" "${END_DATE}" <<'PY'
import sys
from datetime import date, timedelta
d0 = date(int(sys.argv[1][0:4]), int(sys.argv[1][4:6]), int(sys.argv[1][6:8]))
d1 = date(int(sys.argv[2][0:4]), int(sys.argv[2][4:6]), int(sys.argv[2][6:8]))
if d1 < d0:
    sys.exit("END_DATE is before START_DATE")
n = (d1 - d0).days + 1
for i in range(n):
    print((d0 + timedelta(days=i)).strftime("%Y%m%d"))
PY
)"
NDAYS="$(wc -l <<<"${DAY_LIST}")"

echo "=== get_forcing_ecfs ==="
echo "range       : ${START_DATE} .. ${END_DATE}  (${NDAYS} days)"
echo "source      : ${ECFS_DIR}/${PREFIX}_<YYYYMMDD>.tar.gz"
echo "destination : ${DEST_DIR}"
echo "concurrency : ${CONCURRENCY}"
echo

fetch_one() {
  local d="$1"
  local dest="${DEST_DIR}/${PREFIX}_${d}.tar.gz"
  if [[ -s "${dest}" ]]; then
    echo "SKIP  ${d}  (already present)"
    return 0
  fi
  if ecp "${ECFS_DIR}/${PREFIX}_${d}.tar.gz" "${DEST_DIR}/" >/dev/null 2>"${dest}.err"; then
    rm -f "${dest}.err"
    echo "OK    ${d}"
  else
    echo "FAIL  ${d}  (see ${dest}.err)"
    return 1
  fi
}
export -f fetch_one
export DEST_DIR ECFS_DIR PREFIX

echo "${DAY_LIST}" | xargs -P "${CONCURRENCY}" -I{} bash -c 'fetch_one "$@"' _ {}

echo
echo "-- summary --"
TOTAL_PRESENT="$(find "${DEST_DIR}" -maxdepth 1 -name "${PREFIX}_*.tar.gz" | wc -l)"
echo "present in ${DEST_DIR}: ${TOTAL_PRESENT} / ${NDAYS} requested"
du -sh "${DEST_DIR}" 2>/dev/null || true
FAILED="$(find "${DEST_DIR}" -maxdepth 1 -name "*.err" | wc -l)"
if [[ "${FAILED}" -gt 0 ]]; then
  echo "WARNING: ${FAILED} day(s) failed -- see *.err files in ${DEST_DIR}" >&2
  exit 1
fi

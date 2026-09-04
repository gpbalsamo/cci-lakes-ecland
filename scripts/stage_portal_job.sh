#!/usr/bin/env bash

# Import one ecland-portal job (../ecland-portal, "ecLand Anywhere") into this
# repository's layout, so scripts/ecland_run_experiment.sh can find it.
#
# ecland-portal writes each job to
#   $PERM/ecland_portal_jobs/<job_id>/
#     clim/<group>/surfclim_<STA>.nc, surfinit_<STA>.nc
#     forcing/<group>/met_<ftype>HT_<STA>.nc
#     namelist_<STA>                     (if the namelist step ran)
#     output/<STA>/o_*.nc, restartout.nc (if the run step ran)
#     landgram_<STA>.png                 (if the landgram step ran)
#     request.json, state.txt, status.json
# where <group> is an internal detail (e.g. ECLAND_ANYWHERE, appended by the
# create_forcing tool) and STA is <SITE>_<Y1>-<Y2>.
#
# This repo groups all lakes under GROUP=CCI_LAKES instead, so:
#   clim/<group>/surfclim_<STA>.nc    -> clim/CCI_LAKES/surfclim_<STA>.nc
#   forcing/<group>/met_*HT_<STA>.nc  -> forcing/CCI_LAKES/met_*HT_<STA>.nc
# filenames are kept as-is: ecland_run_experiment.sh's find_sites() strips the
# first two underscore-separated fields off the forcing filename to recover
# <STA>, so no renaming is needed for either engine to agree on the site id.
#
# A namelist and/or output/ already produced by the portal (request.json's
# run_namelist / run_model) are staged too, under a name that keeps them
# distinct from a rerun made with this repo's own namelist variants:
#   output/<STA>__portal_<job_id>/
#
# Safe to re-run: only copies files that are present, skips what is not (the
# job may still be mid-flight), and never overwrites an existing destination
# file without --force.
#
# Usage:
#   stage_portal_job.sh JOB_ID [--link] [--force] [--root JOBS_ROOT]
#
#     JOB_ID    e.g. 20260904T111326_Ld-001
#     --link    symlink instead of copy (saves space; breaks if the job
#                directory is later moved or cleaned up)
#     --force   overwrite files that already exist at the destination
#     --root    JOBS_ROOT, default $ECLAND_PORTAL_JOBS_ROOT or $PERM/ecland_portal_jobs
#
# (C) Copyright 2026- ECMWF. Apache Licence Version 2.0.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd -P)"
GROUP="CCI_LAKES"

usage() {
  awk '/^# Usage:/{p=1} /^# \(C\) Copyright/{p=0} p' "${BASH_SOURCE[0]}" \
    | sed 's/^#[[:space:]]\{0,1\}//'
}

LINK=false
FORCE=false
JOBS_ROOT="${ECLAND_PORTAL_JOBS_ROOT:-${PERM:-/perm/${USER:-pad}}/ecland_portal_jobs}"
JOB_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) LINK=true; shift ;;
    --force) FORCE=true; shift ;;
    --root) JOBS_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -z "${JOB_ID}" ]]; then JOB_ID="$1"; shift
      else echo "ERROR: unexpected argument: $1" >&2; usage >&2; exit 2; fi
      ;;
  esac
done

if [[ -z "${JOB_ID}" ]]; then
  usage >&2
  exit 2
fi

JOB_DIR="${JOBS_ROOT}/${JOB_ID}"
if [[ ! -d "${JOB_DIR}" ]]; then
  echo "ERROR: job directory not found: ${JOB_DIR}" >&2
  exit 1
fi

place() {
  local src="$1" dst="$2"
  if [[ -e "${dst}" && "${FORCE}" != true ]]; then
    echo "  skip (exists): ${dst#${REPO_ROOT}/}"
    return
  fi
  mkdir -p "$(dirname "${dst}")"
  if [[ "${LINK}" == true ]]; then
    ln -sfn "${src}" "${dst}"
    echo "  linked: ${dst#${REPO_ROOT}/}"
  else
    cp -p "${src}" "${dst}"
    echo "  copied: ${dst#${REPO_ROOT}/}"
  fi
}

echo "=== staging ${JOB_ID} ==="
echo "job dir : ${JOB_DIR}"
[[ -f "${JOB_DIR}/state.txt" ]] && echo "state   : $(cat "${JOB_DIR}/state.txt")"

echo
echo "-- clim --"
CLIM_COUNT=0
while IFS= read -r -d '' f; do
  place "${f}" "${REPO_ROOT}/clim/${GROUP}/$(basename "${f}")"
  CLIM_COUNT=$((CLIM_COUNT + 1))
done < <(find "${JOB_DIR}/clim" -maxdepth 2 \( -name "surfclim_*.nc" -o -name "surfinit_*.nc" \) -print0 2>/dev/null)
[[ "${CLIM_COUNT}" -eq 0 ]] && echo "  none yet (physiography step not finished?)"

echo
echo "-- forcing --"
FORCING_COUNT=0
while IFS= read -r -d '' f; do
  place "${f}" "${REPO_ROOT}/forcing/${GROUP}/$(basename "${f}")"
  FORCING_COUNT=$((FORCING_COUNT + 1))
done < <(find "${JOB_DIR}/forcing" -maxdepth 2 -name "met_*.nc" -print0 2>/dev/null)
[[ "${FORCING_COUNT}" -eq 0 ]] && echo "  none yet (forcing step not finished?)"

echo
echo "-- namelist (if the portal already generated one) --"
shopt -s nullglob
NAMELISTS=("${JOB_DIR}"/namelist_*)
shopt -u nullglob
if [[ ${#NAMELISTS[@]} -eq 0 ]]; then
  echo "  none yet"
else
  for nl in "${NAMELISTS[@]}"; do
    [[ -f "${nl}" ]] || continue
    STA="$(basename "${nl}")"; STA="${STA#namelist_}"
    place "${nl}" "${REPO_ROOT}/output/${STA}__portal_${JOB_ID}/namelist_${STA}"
  done
fi

echo
echo "-- model output (if the portal already ran ecLand) --"
if [[ -d "${JOB_DIR}/output" ]] && find "${JOB_DIR}/output" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  for sta_dir in "${JOB_DIR}/output"/*/; do
    [[ -d "${sta_dir}" ]] || continue
    STA="$(basename "${sta_dir}")"
    DEST="${REPO_ROOT}/output/${STA}__portal_${JOB_ID}"
    while IFS= read -r -d '' f; do
      place "${f}" "${DEST}/$(basename "${f}")"
    done < <(find "${sta_dir}" -maxdepth 1 -type f -print0)
  done
else
  echo "  none yet"
fi

echo
echo "-- landgram (if the portal already rendered one) --"
shopt -s nullglob
LANDGRAMS=("${JOB_DIR}"/landgram_*.png)
shopt -u nullglob
if [[ ${#LANDGRAMS[@]} -eq 0 ]]; then
  echo "  none yet"
else
  for png in "${LANDGRAMS[@]}"; do
    STA="$(basename "${png}" .png)"; STA="${STA#landgram_}"
    place "${png}" "${REPO_ROOT}/output/${STA}__portal_${JOB_ID}/$(basename "${png}")"
  done
fi

echo
echo "-- provenance --"
PROV_DIR="${REPO_ROOT}/sites/provenance/${JOB_ID}"
mkdir -p "${PROV_DIR}"
for f in request.json status.json forcing_config.yaml physiography_config.yaml; do
  [[ -f "${JOB_DIR}/${f}" ]] && cp -p "${JOB_DIR}/${f}" "${PROV_DIR}/"
done
echo "  recorded under ${PROV_DIR#${REPO_ROOT}/}"

echo
echo "Done. Update sites/lakes.csv's status column by hand if this changes it"
echo "(e.g. forcing_in_progress -> forcing_ready)."

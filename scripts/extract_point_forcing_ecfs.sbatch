#!/bin/bash
#SBATCH --job-name=extract-point-forcing
#SBATCH --qos=nf
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --output=%x-%j.out
#SBATCH --error=%x-%j.err

# Batch wrapper for extract_point_forcing_ecfs.py, so a many-day point
# extraction (one gzip-streaming pass per day, ~1 min/day -- see that
# script's own docstring for the measurement) runs as a queued job rather
# than a login-node process tied to an interactive session.
#
# Submit with the parameters as --export, e.g. a full year for Ladoga:
#   sbatch --export=ALL,RAW_DIR=$SCRATCH/cci-lakes-ecland/forcing/raw,\
#     START_DATE=20170101,END_DATE=20171231,LAT=60.765,LON=31.648,\
#     OUT=$PERM/cci-lakes-ecland/forcing/CCI_LAKES/met_ecfsHT_Ld-001_2017-2017.nc,\
#     WORK_DIR=$SCRATCH/cci-lakes-ecland/forcing/_work_Ld-001_2017-2017 \
#     scripts/extract_point_forcing_ecfs.sbatch
#
# RAW_DIR, START_DATE, END_DATE, LAT, LON and OUT are required; WORK_DIR
# defaults to a temp dir removed on completion -- pass one explicitly (as
# above) to keep it, so an interrupted job resumes instead of restarting.
#
# CACHE_DIR (optional) overrides the shared decompression cache the extractor
# uses by default (a '_decompressed_cache' dir next to RAW_DIR) -- every lake's
# jobs should point at the SAME cache dir, since that is what lets a day
# already decompressed for one lake be skipped for the next rather than
# re-decompressed (see extract_point_forcing_ecfs.py's own docstring for the
# measured saving: ~29% at 2 lakes, ~49% at 7, approaching ~57% as more lakes
# share it). Set NO_CACHE=true to fall back to the pre-cache behaviour instead.
#
# (C) Copyright 2026- ECMWF. Apache Licence Version 2.0.

set -uo pipefail

# See get_forcing_ecfs.sbatch's own note: SLURM copies the submitted script to
# /var/spool/slurmd/job<id>/ and runs it from there, so ${BASH_SOURCE[0]}-based
# path resolution does not find sibling files. Anchor to $PERM instead.
REPO_DIR="${REPO_DIR:-${PERM:?PERM not set in the batch environment}/cci-lakes-ecland}"

: "${RAW_DIR:?set via --export=RAW_DIR=...}"
: "${START_DATE:?set via --export=START_DATE=YYYYMMDD}"
: "${END_DATE:?set via --export=END_DATE=YYYYMMDD}"
: "${LAT:?set via --export=LAT=...}"
: "${LON:?set via --export=LON=...}"
: "${OUT:?set via --export=OUT=...}"

ARGS=(--raw-dir "${RAW_DIR}" --start "${START_DATE}" --end "${END_DATE}"
      --lat "${LAT}" --lon "${LON}" --out "${OUT}")
if [[ -n "${WORK_DIR:-}" ]]; then
  ARGS+=(--keep-work-dir --work-dir "${WORK_DIR}")
fi
if [[ "${NO_CACHE:-false}" == "true" ]]; then
  ARGS+=(--no-cache)
elif [[ -n "${CACHE_DIR:-}" ]]; then
  ARGS+=(--cache-dir "${CACHE_DIR}")
fi

source /etc/profile.d/modules.sh 2>/dev/null || true
module purge
module load prgenv/intel ecmwf-toolbox/new python3/new netcdf4/new cdo/2.2.0

python3 -u "${REPO_DIR}/scripts/extract_point_forcing_ecfs.py" "${ARGS[@]}"

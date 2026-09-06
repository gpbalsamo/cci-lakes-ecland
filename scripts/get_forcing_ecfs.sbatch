#!/bin/bash
#SBATCH --job-name=get-forcing-ecfs
#SBATCH --qos=nf
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --output=%x-%j.out
#SBATCH --error=%x-%j.err

# Batch wrapper for get_forcing_ecfs.sh, so a multi-day ECFS pull runs as a
# proper queued job rather than a login-node process tied to an interactive
# session. CPU/mem needs are trivial (ecp is I/O-bound); the only thing this
# job actually needs is wall clock, capped at qos nf's 2-day MaxWall.
#
# Submit with the parameters as --export, e.g.:
#   sbatch --export=START_DATE=20170101,END_DATE=20230101,DEST_DIR=$SCRATCH/ifs-lakebench/forcing/raw,CONCURRENCY=8 \
#     scripts/get_forcing_ecfs.sbatch
#
# START_DATE and END_DATE are required; DEST_DIR and CONCURRENCY fall back to
# get_forcing_ecfs.sh's own defaults if unset.
#
# (C) Copyright 2026- ECMWF. Apache Licence Version 2.0.

set -uo pipefail

# NOTE: cannot resolve sibling scripts from ${BASH_SOURCE[0]} here -- SLURM
# copies the submitted script to /var/spool/slurmd/job<id>/ and runs it from
# there, so BASH_SOURCE points at the spool copy, not this repo checkout (this
# is why the first submission of this job, 32771319, failed in 8 seconds with
# "get_forcing_ecfs.sh: No such file or directory"). Resolve the repo root
# from $PERM instead, like the sibling repos' own scripts do.
REPO_DIR="${REPO_DIR:-${PERM:?PERM not set in the batch environment}/ifs-lakebench}"

: "${START_DATE:?set via --export=START_DATE=YYYYMMDD}"
: "${END_DATE:?set via --export=END_DATE=YYYYMMDD}"
: "${SCRATCH:?SCRATCH not set in the batch environment}"

DEST_DIR="${DEST_DIR:-${SCRATCH}/ifs-lakebench/forcing/raw}"
CONCURRENCY="${CONCURRENCY:-4}"

"${REPO_DIR}/scripts/get_forcing_ecfs.sh" "${START_DATE}" "${END_DATE}" "${DEST_DIR}" "${CONCURRENCY}"

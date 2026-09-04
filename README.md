# cci-lakes-ecland

Scripts and configuration to run [ecLand](https://www.ecmwf.int/en/research/modelling-systems/land-surface) (specifically its [FLake](https://www.flake.igb-berlin.de/) lake scheme) over lakes from the [ESA Climate Change Initiative Lakes](https://climate.esa.int/en/projects/lakes/) (CCI Lakes) project, and to benchmark the result against CCI-Lakes observations.

Starting point: one lake, **Lake Ladoga** (site `Ld-001`, 60.765N 31.648E), forced from ECMWF operational analysis. See [Current status](#current-status).

## Relationship to sibling repos

This repo does not re-derive the ecLand run/namelist machinery; it reuses it.

| Repo | What it contributes here |
|---|---|
| [`../plumber2-ecland`](../plumber2-ecland) | Source of `scripts/ecland_run_experiment.sh`, `ecland_run_model.sh`, `ecland_runtime.sh` and `ecland_create_namelist.py`, vendored into `scripts/` unmodified (they are already generic over site group and forcing type — nothing here is PLUMBER2-specific). Also the source namelist for `namelists/namelist_ecland_lake_ctl`. |
| [`../ecland-portal`](../ecland-portal) ("ecLand Anywhere") | Produces the physiography (`surfclim`/`surfinit`) for an arbitrary lat/lon — including `which_surface: lake`, which forces 100% lake fraction so FLake actually runs. `scripts/stage_portal_job.sh` imports one of its job directories into this repo's layout. |

Unlike the two flux-tower repos (`plumber2-ecland`'s 170 PLUMBER2 sites, `fluxnet-shuttle-ecland`'s 775 FLUXNET sites), there is no in-situ forcing or observation dataset to pull from Git LFS here: physiography comes from an ecland-portal extraction, forcing from ECFS (see below), and the evaluation data is a satellite product (CCI-Lakes), not a flux tower.

**Forcing does *not* come from ecland-portal's own MARS retrieval.** That path (`run_forcing: true`, whole-month MARS requests) runs at roughly 1 hour of wall clock per month spanned, which made a 6-year pull impractical — the first attempt (job `20260904T111326_Ld-001`) was cancelled after 51 minutes, still in its first month. ECFS already holds the same `class od stream oper expver 1` fields as daily global GRIB tarballs going back to at least 2016, at `/paga/OSM_FORCING/forcing_od_1_oper_1_<YYYYMMDD>.tar.gz` (~2.1 GB/day for 2017 onward). `scripts/get_forcing_ecfs.sh` pulls those with `ecp` instead, skipping MARS entirely. This only stages the raw global GRIB, though — turning it into ecLand-ready, point-extracted forcing (the equivalent of `met_*HT_*.nc`) is a separate step, not yet written (see [Open work](#open-work)).

## Current status

Only Ladoga (`Ld-001`) is registered so far — see `sites/lakes.csv`. Benchmark period: **2017-2022** (6 full calendar years); forcing is fetched through 2023-01-01 00:00 since ecLand needs that instant as the boundary driving the last timestep of 2022 (see `../ecland-portal`'s README, "The simulated period, and NSTOP").

- **Physiography** (`clim/CCI_LAKES/surfclim_Ld-001_2017-2022.nc`, `surfinit_...`): done. Staged from ecland-portal job `20260904T120600_Ld-001` (a physiography-only rerun) and relabelled from its `2017-2026` placeholder end-date to `2017-2022` with `stage_portal_job.sh --years` — surfclim/surfinit don't depend on end_date at all, so no re-extraction was needed.
- **Forcing**: downloading. `get_forcing_ecfs.sh 20170101 20230101` (2192 days, ~4.5 TB) is running as SLURM job `32771319` (`scripts/get_forcing_ecfs.sbatch`, ~24h wall clock at concurrency 8) into `$SCRATCH/cci-lakes-ecland/forcing/raw/`. Check progress with `squeue -u $USER -n get-forcing-ecfs` or `ls $SCRATCH/cci-lakes-ecland/forcing/raw | wc -l` (2192 when complete).
- **Point extraction + metview processing** of the raw daily GRIB into ecLand-ready forcing: not started. **Model run, post-processing and benchmarking**: not started — see [Open work](#open-work).

## Quick start

### 1. Fetch forcing from ECFS

```bash
scripts/get_forcing_ecfs.sh 20170101 20230101
# or, for a run long enough to want a queued job instead of a login-node process:
sbatch --export=ALL,START_DATE=20170101,END_DATE=20230101 scripts/get_forcing_ecfs.sbatch
```

Defaults to `$SCRATCH/cci-lakes-ecland/forcing/raw/`, concurrency 8 (tested: faster than serial, but 16 was *slower* than 8 — ECFS/tape access seems to throttle somewhere around there). Safe to re-run or resume: `ecp`'s default `-n` behaviour skips a destination file that already exists.

### 2. Stage a lake's ecland-portal (physiography) job

```bash
scripts/stage_portal_job.sh 20260904T120600_Ld-001 --years 2017-2022
```

Copies whatever the job has produced — `clim/CCI_LAKES/`, `forcing/CCI_LAKES/` (only relevant for a job that still uses ecland-portal's own MARS forcing step), and, if the portal ran further steps, the generated namelist, model output and landgram figure under `output/<STA>__portal_<job_id>/` — and records `request.json`/`forcing_config.yaml`/`physiography_config.yaml` under `sites/provenance/<job_id>/`. Safe to re-run; it skips files already staged unless `--force` is given. Add `--link` to symlink instead of copy, or `--years Y1-Y2` to relabel filenames whose `<Y1>-<Y2>` suffix reflects a placeholder end_date rather than the actual benchmark period (create_forcing names files by the literal year digits of `--endDate`, not by what the run is meant to represent).

### 3. Turn the raw GRIB into ecLand-ready forcing

Not written yet — see [Open work](#open-work). Once it exists, this produces `forcing/CCI_LAKES/met_*_Ld-001_2017-2022.nc` from `forcing/raw/`.

### 4. Run (or re-run with a different namelist)

```bash
scripts/ecland_run_experiment.sh \
  -g CCI_LAKES \
  -t <forcing-type-from-step-3> \
  -s Ld-001_2017-2022 \
  -n namelists/namelist_ecland_lake_ctl \
  -x <path_to_ecland_executable>
```

`-n` defaults to `namelists/namelist_ecland_lake_ctl` if omitted. If a portal job's own run was staged instead (`output/<STA>__portal_<job_id>/`, see step 2), that is already a valid simulation and this step is only needed for a namelist variant.

### 5. Post-process and benchmark

```bash
python3 scripts/postproc_lake.py --inputdir output --outdir postprocessed
python3 scripts/benchmark_lake.py --model-dir postprocessed --obs-dir obs --out-dir benchmark/dashboards/<run-name>
```

Both are currently stubs — see [Open work](#open-work).

## Namelists

`namelists/namelist_ecland_lake_ctl` is plumber2-ecland's `namelist_ecland_50R1_ctl` with one change: `LWRLKE=.TRUE.` (plumber2's copy has it off — "not active for now"), so the run writes `o_lke.nc`, the FLake state needed to score against CCI-Lakes. `LEFLAKE=.TRUE.` was already on in the source namelist: FLake runs at any grid point with lake fraction, land run or not.

Name new variants `namelist_ecland_lake_<variant>`, matching the plumber2-ecland convention.

## Repository layout

```
cci-lakes-ecland/
├── sites/
│   ├── lakes.csv                # registry: one row per lake (site_id, lat/lon, dates, portal job, status)
│   └── provenance/<job_id>/     # request.json etc. from each staged ecland-portal job -- not in git
├── namelists/                   # ecLand namelist configurations
├── scripts/
│   ├── get_forcing_ecfs.sh      # fetch daily raw 'oper' GRIB tarballs from ECFS
│   ├── get_forcing_ecfs.sbatch  # \_ batch wrapper, for a multi-day pull
│   ├── stage_portal_job.sh      # import an ecland-portal job into this repo's layout
│   ├── ecland_run_experiment.sh # run one or more site experiments (vendored from plumber2-ecland)
│   ├── ecland_run_model.sh      # \_ vendored from plumber2-ecland, unmodified engine logic
│   ├── ecland_runtime.sh        # /
│   ├── ecland_create_namelist.py# /
│   ├── postproc_lake.py         # STUB: raw ecLand output -> lake variable schema
│   └── benchmark_lake.py        # STUB: score against ESA-CCI-Lakes observations
├── clim/CCI_LAKES/              # staged physiography/init (NetCDF) -- not in git
├── forcing/
│   ├── raw/                     # daily global GRIB tarballs from ECFS -- not in git
│   ├── logs/                    # get_forcing_ecfs.sbatch stdout/stderr -- not in git
│   └── CCI_LAKES/               # ecLand-ready, point-extracted forcing (NetCDF) -- not in git
├── obs/                         # ESA-CCI-Lakes observational product -- not sourced yet, not in git
├── output/                      # raw model output -- not in git
├── postprocessed/               # post-processed output -- not in git
└── benchmark/dashboards/        # metrics + dashboard per run -- checked in, once real
```

Note: `forcing/raw/` and `forcing/logs/` above live under `$SCRATCH/cci-lakes-ecland/forcing/` (~4.5 TB for the full Ladoga pull), not under this repository's own tree — the layout is shown here because it's still keyed to this repo's convention for where forcing lives, just relocated for the disk space.

## Open work

- **Write the point-extraction / metview processing step** that turns `forcing/raw/*.tar.gz` (global daily GRIB) into ecLand-ready, point-extracted forcing NetCDF for Ladoga — the ECFS equivalent of what `../ecland-portal`'s `extract_create_forcing.bash` does for a fresh MARS retrieval (see its `osm_pyutils/process_site_var.py` for the point-selection logic to reuse rather than reimplement).
- **Source the ESA-CCI-Lakes observational product.** Most likely the lake surface water temperature (LSWT) product; possibly also ice cover/duration. Nothing CCI-Lakes-shaped was found under `$PERM` while setting this repo up.
- **Implement `postproc_lake.py`** once a run has produced a real `o_lke.nc` to inspect — confirm FLake's output variable names against that file (or `yos_flake.F90` in the ecLand source) rather than guessing them ahead of time.
- **Implement `benchmark_lake.py`** once both of the above exist — likely following `plumber2-ecland/scripts/benchmark_plumber2.py`'s shape (per-site scores, self-contained HTML dashboard), scored per lake instead of per flux tower.
- **Add more lakes** to `sites/lakes.csv` as further ecland-portal jobs are run for them.

## License

Copyright 2026- ECMWF. Licensed under the [Apache Licence Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

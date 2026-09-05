# cci-lakes-ecland

Scripts and configuration to run [ecLand](https://www.ecmwf.int/en/research/modelling-systems/land-surface) (specifically its [FLake](https://www.flake.igb-berlin.de/) lake scheme) over lakes from the [ESA Climate Change Initiative Lakes](https://climate.esa.int/en/projects/lakes/) (CCI Lakes) project, and to benchmark the result against CCI-Lakes observations.

Starting point: one lake, **Lake Ladoga** (site `Ld-001`, 60.765N 31.648E), forced from ECMWF operational analysis. The full 2017-2022 benchmark period has been simulated end-to-end and properly spun up; six candidate lakes (`sites/candidate_lakes.csv`) are now moving through the same pipeline. See [Current status](#current-status).

## Relationship to sibling repos

This repo does not re-derive the ecLand run/namelist machinery; it reuses it.

| Repo | What it contributes here |
|---|---|
| [`../plumber2-ecland`](../plumber2-ecland) | Source of `scripts/ecland_run_experiment.sh`, `ecland_run_model.sh`, `ecland_runtime.sh` and `ecland_create_namelist.py`, vendored into `scripts/` unmodified (they are already generic over site group and forcing type — nothing here is PLUMBER2-specific). Also the source namelist for `namelists/namelist_ecland_lake_ctl`. |
| [`../ecland-portal`](../ecland-portal) ("ecLand Anywhere") | Produces the physiography (`surfclim`/`surfinit`) for an arbitrary lat/lon — including `which_surface: lake`, which forces 100% lake fraction so FLake actually runs. `scripts/stage_portal_job.sh` imports one of its job directories into this repo's layout. |

Unlike the two flux-tower repos (`plumber2-ecland`'s 170 PLUMBER2 sites, `fluxnet-shuttle-ecland`'s 775 FLUXNET sites), there is no in-situ forcing or observation dataset to pull from Git LFS here: physiography comes from an ecland-portal extraction, forcing from ECFS (see below), and the evaluation data is a satellite product (CCI-Lakes), not a flux tower.

**Forcing does *not* come from ecland-portal's own MARS retrieval.** That path (`run_forcing: true`, whole-month MARS requests) runs at roughly 1 hour of wall clock per month spanned, which made a 6-year pull impractical — the first attempt (job `20260904T111326_Ld-001`) was cancelled after 51 minutes, still in its first month. ECFS already holds the same `class od stream oper expver 1` fields as daily global GRIB tarballs going back to at least 2016, at `/paga/OSM_FORCING/forcing_od_1_oper_1_<YYYYMMDD>.tar.gz` (~2.1 GB/day for 2017 onward). `scripts/get_forcing_ecfs.sh` pulls those with `ecp` instead, skipping MARS entirely, and `scripts/extract_point_forcing_ecfs.py` turns the raw global GRIB into ecLand-ready, point-extracted forcing.

`../ecland-portal` has since grown its own `use_forcing_archive` request option pointing at this same `forcing/raw/` archive and this same extractor script (see its `config/defaults.yaml`'s `forcing_archive` block) — so a portal job *can* read from the archive natively. It is not used for the multi-year runs in this repo, though: the orchestrator's per-job wall-clock budget defaults to 90 minutes (`GET /healthz`'s `time_limit`), far short of what even a single year's extraction needs (~7-8h), so a portal request spanning more than a few days would simply time out. This repo keeps forcing extraction as its own directly-submitted, per-year SLURM jobs (see step 3) for that reason — only physiography goes through the portal.

## Current status

See `sites/lakes.csv` (lakes with a full pipeline run) and `sites/candidate_lakes.csv` (lakes in progress or not yet started). Benchmark period for all lakes: **2017-2022** (6 full calendar years); forcing is fetched through 2023-01-01 00:00 since ecLand needs that instant as the boundary driving the last timestep of 2022 (see `../ecland-portal`'s README, "The simulated period, and NSTOP").

### Ladoga (`Ld-001`) — complete

- **Physiography** (`clim/CCI_LAKES/surfclim_Ld-001_2017-2022.nc`, `surfinit_...`): done. Staged from ecland-portal job `20260904T120600_Ld-001` (a physiography-only rerun) and relabelled from its `2017-2026` placeholder end-date to `2017-2022` with `stage_portal_job.sh --years` — surfclim/surfinit don't depend on end_date at all, so no re-extraction was needed.
- **Forcing**: done. The full 2017-2022 raw daily GRIB (2192 days, 4.2 TB) is in `$SCRATCH/cci-lakes-ecland/forcing/raw/` — this is a *global* archive, reused as-is for every other lake too, no new ECFS download needed per lake.
- **Point extraction and merge**: done. `scripts/extract_point_forcing_ecfs.py` run once per year (2018-2022 in parallel — safer than one ~48h job given the final NetCDF is only written once every day for every variable is done), then `scripts/merge_yearly_forcing.py` joined the six years into `forcing/CCI_LAKES/met_ecfsHT_Ld-001_2017-2022.nc` (52585 uniformly-spaced hourly timesteps, no gaps, no NaNs).
- **Model run**: the full 2017-2022 period has been simulated end-to-end and **properly spun up** (see [Full benchmark-period run](#full-benchmark-period-run-validated-spun-up)), on top of the earlier 10-day smoke test and full-year spin-up check — see [Known issues](#known-issues) before running further. **Post-processing and benchmarking**: not started — see [Open work](#open-work).

### Candidate lakes — in progress

Six lakes from `sites/candidate_lakes.csv` (Baringo, Chilwa, Kyoga, Mweru Wantipa, Tana, Victoria) are moving through the same pipeline: an ecland-portal physiography-only job per lake (mirroring Ladoga's `20260904T120600_Ld-001`), plus 6 years × 6 lakes = 36 parallel per-year point-extraction jobs against the already-downloaded raw archive (no new ECFS transfer needed). Once both finish per lake: merge, generate the namelist, spin-up check, then a properly spun-up full-period run — the same four steps Ladoga already went through.

### End-to-end smoke test (validated)

Confirms the full pipeline works: ECFS fetch → point extraction → namelist → ecLand run → physically sensible FLake output.

```bash
python3 scripts/extract_point_forcing_ecfs.py \
  --raw-dir $SCRATCH/cci-lakes-ecland/forcing/raw \
  --start 20170101 --end 20170110 --lat 60.765 --lon 31.648 \
  --out forcing/CCI_LAKES/met_ecfsHT_Ld-001_2017-2017.nc
# clim/CCI_LAKES/{surfclim,surfinit}_Ld-001_2017-2017.nc copied from the
# 2017-2022 versions (content is identical for this sub-range)
python3 scripts/ecland_create_namelist.py -g CCI_LAKES \
  -n namelists/namelist_ecland_lake_ctl -s Ld-001_2017-2017 \
  -d . -w output -t ecfs
# then hand-correct NSTOP: nforcing-2 -> nforcing-1 (239 -> 240 here; see the
# NSTOP note under step 4 below) before running
```

Result: `AvgSurfT` cools from 274.71 K to 271.9 K over the 10 days (a January cold snap), the surface freezes (hits 273.15 K and holds), and ice forms (`HLICE` 0 → 0.16 m) — physically exactly what's expected for Ladoga in January. **This only works with the right ecland-master binary — see Known issues.**

### Spin-up / convergence check (validated)

Once a full year of forcing exists, `ecland_run_model.sh -l N` repeats it N times, each loop restarting from the previous loop's end state (`ecland_run_model.sh`'s existing spin-up mechanism — no new script needed for the run itself). `scripts/check_spinup_convergence.py OUTPUT_DIR N` reads the end-of-year FLake state (`AvgSurfT`, `TLMNW`, `TLWML`, `TLBOT`, `HLML`, `HLICE`) from every loop's `o_gg_S<n>.nc` and reports how far apart consecutive loops are — the standard spin-up diagnostic.

Run for Ladoga, full 2017, 8 loops: end-of-year state stabilises within 2-3 loops (loop 1→2 changes by up to 0.35 K / 0.35 m; by loop 5→8 the largest change is under 0.0005 K) — Ladoga's ~66 m depth spins up fast in FLake's bulk mixed-layer scheme. Worth re-checking per lake once the candidates in `sites/candidate_lakes.csv` are run: a shallower lake (e.g. Chilwa, 2 m mean depth) should converge even faster; whether depth vs. convergence speed holds as a general pattern across the set is an open question.

### Full benchmark-period run (validated, spun up)

With all six years merged (see step 3 below), a single `ecland_run_model.sh -l 1` pass over 2017-2022 (52584 hourly steps) runs in ~2 minutes on `ecland-master-dp`. No NaNs, no drift: `AvgSurfT` stays in [253, 295] K across the whole period, ice covers ~23% of hours, and end-of-year state varies year to year (274-277 K) the way real inter-annual variability should, not runaway divergence.

**This is now a properly spun-up run, not a cold start.** The initial cold-start pass (surfinit from ecland-portal) showed a small but real transient in year 1 (2017 end-of-year `AvgSurfT` differed by 0.033 K from the spun-up version, 2018 by 0.003 K, 2019 onward identical to 4 decimals) — consistent with the spin-up check above needing 2-3 loops to converge. To remove that transient: run the spin-up check's final loop restart (`output/Ld-001_2017-2017/restartout.nc`, the loop-8 equilibrium state from a single representative year) as the *initial conditions* for the full-period run, in place of ecland-portal's own cold-start `surfinit`/`surfclim`:

```bash
mkdir -p clim/CCI_LAKES_spunup
cp output/Ld-001_2017-2017/restartout.nc clim/CCI_LAKES_spunup/surfinit_Ld-001_2017-2022.nc
cp output/Ld-001_2017-2017/restartout.nc clim/CCI_LAKES_spunup/surfclim_Ld-001_2017-2022.nc
```

A `restartout.nc` can stand in for both `surfinit` and `surfclim` inputs because that is exactly what `ecland_run_model.sh`'s own `-l N` loop-chaining already does internally between loops (`ln -sf restartout_S${RLOOP}.nc soilinit` / `surfclim`) — this just does the same substitution across two separate invocations instead of within one. Then point `-i` at `clim/CCI_LAKES_spunup` instead of `clim/CCI_LAKES` for the scored run (see step 4). The cold-start run is kept alongside (`output/Ld-001_2017-2022/`) for comparison; the spun-up one (`output_spunup/Ld-001_2017-2022/`) is the one to score against observations.

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

For more than a year or so, run one extraction **per calendar year** rather than one call for the whole range: each variable-day takes roughly a minute, and the final NetCDF is only written after every day for every variable is done — a single job for a multi-year range risks losing the entire result to a wall-clock timeout after finishing almost everything. `scripts/extract_point_forcing_ecfs.sbatch` makes this a queued job; submit one per year (they can run in parallel):

```bash
for YEAR in 2017 2018 2019 2020 2021 2022; do
  sbatch --export=ALL,RAW_DIR=$SCRATCH/cci-lakes-ecland/forcing/raw,\
START_DATE=${YEAR}0101,END_DATE=${YEAR}1231,LAT=60.765,LON=31.648,\
OUT=$PWD/forcing/CCI_LAKES/met_ecfsHT_Ld-001_${YEAR}-${YEAR}.nc,\
WORK_DIR=$SCRATCH/cci-lakes-ecland/forcing/_work_Ld-001_${YEAR}-${YEAR} \
    scripts/extract_point_forcing_ecfs.sbatch
done
```

Each call crops the global daily GRIB to the point, drops the one-instant overlap between consecutive days, and writes the same schema `ecland_create_namelist.py` and the model already expect. Resumable (`--work-dir`/`WORK_DIR` keeps per-day intermediates; a day already cropped is reused rather than re-fetched/re-cropped). Needs the create_forcing extraction module set (`ecmwf-toolbox/new python3/new netcdf4/new`, plus `cdo`), not the model-run set — see [Known issues](#known-issues).

Then merge the per-year files into one, in chronological order:

```bash
python3 scripts/merge_yearly_forcing.py \
  forcing/CCI_LAKES/met_ecfsHT_Ld-001_2017-2017.nc \
  forcing/CCI_LAKES/met_ecfsHT_Ld-001_2018-2018.nc \
  forcing/CCI_LAKES/met_ecfsHT_Ld-001_2019-2019.nc \
  forcing/CCI_LAKES/met_ecfsHT_Ld-001_2020-2020.nc \
  forcing/CCI_LAKES/met_ecfsHT_Ld-001_2021-2021.nc \
  forcing/CCI_LAKES/met_ecfsHT_Ld-001_2022-2022.nc \
  --out forcing/CCI_LAKES/met_ecfsHT_Ld-001_2017-2022.nc
```

Each per-year file's last timestep duplicates the next year's first (both are the Jan 1 00:00 boundary instant a year's extraction keeps so the model has what it needs to drive December's final hour) — the merge script checks for and drops that duplicate, and converts each file's own per-year time origin onto one continuous axis, refusing to write anything if the result isn't uniformly spaced.

### 4. Spin up, then generate the namelist and run

Generate a namelist for every site-years string you'll run (both the single-year spin-up and the full-period run need one):

```bash
python3 scripts/ecland_create_namelist.py \
  -g CCI_LAKES -n namelists/namelist_ecland_lake_ctl \
  -s Ld-001_2017-2022 -d . -w output -t ecfs
```

**Fix `NSTOP` by hand before running** — the generator computes `nforcing - 2`, one short of the permitted maximum `nforcing - 1` (see `../ecland-portal`'s README, "The simulated period, and NSTOP" — the same off-by-one plumber2-ecland's copy of this script has).

**4a. Spin up** on one representative year (2017), looped until the end-of-year lake state stops changing:

```bash
scripts/ecland_run_model.sh -s Ld-001_2017-2017 -b <ecland-master-dp> \
  -w scripts/work -o output -f forcing/CCI_LAKES -i clim/CCI_LAKES \
  -F ecfs -n output/namelist_Ld-001_2017-2017 -l 8 -R false
python3 scripts/check_spinup_convergence.py output/Ld-001_2017-2017 8
```

**4b. Run the full period**, seeded from that spin-up's equilibrium state instead of the cold-start `surfinit`/`surfclim` (see [Full benchmark-period run](#full-benchmark-period-run-validated-spun-up) for why a `restartout.nc` can stand in for both):

```bash
mkdir -p clim/CCI_LAKES_spunup output_spunup
cp output/Ld-001_2017-2017/restartout.nc clim/CCI_LAKES_spunup/surfinit_Ld-001_2017-2022.nc
cp output/Ld-001_2017-2017/restartout.nc clim/CCI_LAKES_spunup/surfclim_Ld-001_2017-2022.nc
scripts/ecland_run_model.sh -s Ld-001_2017-2022 -b <ecland-master-dp> \
  -w scripts/work -o output_spunup -f forcing/CCI_LAKES -i clim/CCI_LAKES_spunup \
  -F ecfs -n output/namelist_Ld-001_2017-2022 -l 1 -R false
```

**The executable choice matters more than anything else here — see [Known issues](#known-issues) before picking one.** If a portal job's own run was staged instead (`output/<STA>__portal_<job_id>/`, see step 2), that is already a valid (though not spun-up) simulation.

### 5. Post-process and benchmark

```bash
python3 scripts/postproc_lake.py --inputdir output --outdir postprocessed
python3 scripts/benchmark_lake.py --model-dir postprocessed --obs-dir obs --out-dir benchmark/dashboards/<run-name>
```

Both are currently stubs — see [Open work](#open-work).

## Namelists

`namelists/namelist_ecland_lake_ctl` is plumber2-ecland's `namelist_ecland_50R1_ctl`, unchanged except for the model id string. `LEFLAKE=.TRUE.` was already on in the source namelist: FLake runs at any grid point with lake fraction, land run or not. `LWRLKE` is left `.FALSE.` — see [Known issues](#known-issues) for why, and for where lake state actually comes from instead (`o_gg.nc`, not `o_lke.nc`).

Name new variants `namelist_ecland_lake_<variant>`, matching the plumber2-ecland convention.

## Known issues

**The ecland-master binary you pick matters more than anything in the namelist, and picking the wrong one fails silently.** Confirmed 2026-09-04 on the 10-day Ladoga smoke test: `/perm/pad/ecland-build/bin/ecland-master` (single-precision) runs to completion, writes all expected output files, and reports no error — but every FLake variable in `o_gg.nc` (`AvgSurfT`, `TLMNW`, `TLWML`, `TLBOT`, `HLICE`, `HLML`) jumps to a constant default (288.15 K / 50 m) after the *first* timestep and never moves again, for the entire run. `/perm/pad/ecland/build/bin/ecland-master-dp` (double-precision), run against the byte-identical namelist, forcing and physiography, instead produces a physically evolving lake state (cooling, then freezing, in a January cold snap) — matching an independent reference run (ecland-portal job `20260904T145308_Ld-004`, MARS-forced, 1 day) exactly on the overlapping period. **Use `ecland-master-dp`.** The single-precision build is not merely lower-precision here; something in it silently drops FLake to a fallback state.

**`o_lke.nc` cannot be produced by any locally available build.** Tried with `LWRLKE=.TRUE.` on all four builds under `$PERM` (`ecland-build`, `ecland-build_dev`, `ecland-build_v1.0`, and `ecland-master-dp` itself) — every one aborts with `NETCDF-FILE o_lke.nc not Available ! check previous model versions`; the namelist flag exists but the writer isn't compiled into any of these binaries. This doesn't block anything, though: `o_gg.nc` already carries FLake's complete prognostic state per grid point (see the namelist's own comment for the field list) — that's what `scripts/postproc_lake.py` should read once it's implemented, not `o_lke.nc`.

**`ecland_run_model.sh` needs its output directory pre-created.** `abs_path()` on `OUTPUTDIR/STA` runs before the script's own `mkdir -p ${OUTPUTDIR}`, so a fresh `-o` target fails with a `cd: No such file or directory` from inside `abs_path`, not a clearer error at the point of use. `ecland_run_experiment.sh` doesn't hit this (its `OUTPUT_DIR` defaults to an existing `output/`, or you're expected to have created a custom one) — but calling `ecland_run_model.sh` directly, as the smoke test above does, needs `mkdir -p output` (or whatever `-o` names) first.

## Repository layout

```
cci-lakes-ecland/
├── sites/
│   ├── lakes.csv                # registry: one row per lake actually staged/run (site_id, lat/lon, dates, portal job, status)
│   ├── candidate_lakes.csv      # lakes to try next -- physical parameters only, not yet extracted
│   └── provenance/<job_id>/     # request.json etc. from each staged ecland-portal job -- not in git
├── namelists/                   # ecLand namelist configurations
├── scripts/
│   ├── get_forcing_ecfs.sh      # fetch daily raw 'oper' GRIB tarballs from ECFS
│   ├── get_forcing_ecfs.sbatch  # \_ batch wrapper, for a multi-day pull
│   ├── extract_point_forcing_ecfs.py    # crop raw GRIB to one point -> ecLand-ready forcing NetCDF (run per year)
│   ├── extract_point_forcing_ecfs.sbatch # \_ batch wrapper, for a multi-day extraction
│   ├── merge_yearly_forcing.py  # join per-year forcing files into one, dropping the year-boundary duplicate
│   ├── stage_portal_job.sh      # import an ecland-portal job into this repo's layout
│   ├── ecland_run_experiment.sh # run one or more site experiments (vendored from plumber2-ecland)
│   ├── ecland_run_model.sh      # \_ vendored from plumber2-ecland, unmodified engine logic
│   ├── ecland_runtime.sh        # /
│   ├── ecland_create_namelist.py# /
│   ├── check_spinup_convergence.py # read end-of-loop FLake state from an -l N run, report loop-to-loop change
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

- **Finish the candidate lakes.** Physiography is staged for all six (Baringo, Chilwa, Kyoga, Mweru Wantipa, Tana, Victoria — all confirmed 100% lake fraction, depths in the right ballpark against `sites/candidate_lakes.csv`'s reference values). Per-year forcing extraction (36 jobs, 6 lakes × 6 years, against the already-downloaded raw archive) is running. Once done per lake: merge (step 3), spin-up check (step 4a), spun-up full-period run (step 4b) — same four steps Ladoga went through. Move each from `candidate_lakes.csv` into `sites/lakes.csv` as it completes.
- **Source the ESA-CCI-Lakes observational product.** Most likely the lake surface water temperature (LSWT) product; possibly also ice cover/duration. Nothing CCI-Lakes-shaped was found under `$PERM` while setting this repo up.
- **Implement `postproc_lake.py`** to read the FLake fields from `o_gg.nc` (see [Known issues](#known-issues) for the field list — confirmed present, physically evolving and stable across a full 6-year run) into whatever schema `benchmark_lake.py` ends up scoring against.
- **Implement `benchmark_lake.py`** once both of the above exist — likely following `plumber2-ecland/scripts/benchmark_plumber2.py`'s shape (per-site scores, self-contained HTML dashboard), scored per lake instead of per flux tower.

## License

Copyright 2026- ECMWF. Licensed under the [Apache Licence Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

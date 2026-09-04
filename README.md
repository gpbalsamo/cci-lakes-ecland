# cci-lakes-ecland

Scripts and configuration to run [ecLand](https://www.ecmwf.int/en/research/modelling-systems/land-surface) (specifically its [FLake](https://www.flake.igb-berlin.de/) lake scheme) over lakes from the [ESA Climate Change Initiative Lakes](https://climate.esa.int/en/projects/lakes/) (CCI Lakes) project, and to benchmark the result against CCI-Lakes observations.

Starting point: one lake, **Lake Ladoga** (site `Ld-001`, 60.765N 31.648E), forced from ECMWF operational analysis via an in-flight [ecland-portal](../ecland-portal) extraction job. See [Current status](#current-status).

## Relationship to sibling repos

This repo does not re-derive the ecLand run/namelist machinery; it reuses it.

| Repo | What it contributes here |
|---|---|
| [`../plumber2-ecland`](../plumber2-ecland) | Source of `scripts/ecland_run_experiment.sh`, `ecland_run_model.sh`, `ecland_runtime.sh` and `ecland_create_namelist.py`, vendored into `scripts/` unmodified (they are already generic over site group and forcing type — nothing here is PLUMBER2-specific). Also the source namelist for `namelists/namelist_ecland_lake_ctl`. |
| [`../ecland-portal`](../ecland-portal) ("ecLand Anywhere") | Produces the physiography (`surfclim`/`surfinit`) and forcing (`met_*HT_*.nc`) for an arbitrary lat/lon — including `which_surface: lake`, which forces 100% lake fraction so FLake actually runs. `scripts/stage_portal_job.sh` imports one of its finished (or partially finished) job directories into this repo's layout. |

Unlike the two flux-tower repos (`plumber2-ecland`'s 170 PLUMBER2 sites, `fluxnet-shuttle-ecland`'s 775 FLUXNET sites), there is no in-situ forcing or observation dataset to pull from Git LFS here: each lake's forcing comes from an ecland-portal extraction against ERA5/operational analysis, and the evaluation data is a satellite product (CCI-Lakes), not a flux tower.

## Current status

Only Ladoga (`Ld-001`) is registered so far — see `sites/lakes.csv`. Its ecland-portal job (`20260904T111326_Ld-001`) was still in the `forcing` step as of 2026-09-04, retrieving `oper`-class forcing over 2017-01-01 to 2026-01-01. A 9-year, whole-month-per-request MARS retrieval runs at roughly 1 hour per month spanned (per `../ecland-portal`'s README), so this is expected to take a while. The job also requested the namelist and model-run steps (`run_namelist`/`run_model`: `true` in its `request.json`), so once it completes there will already be one full ecLand simulation for Ladoga, produced by the portal itself.

Nothing has been benchmarked yet — no ESA-CCI-Lakes observational data has been located locally, and `scripts/postproc_lake.py` / `scripts/benchmark_lake.py` are stubs. See [Open work](#open-work).

## Quick start

### 1. Stage a lake's ecland-portal job

```bash
scripts/stage_portal_job.sh 20260904T111326_Ld-001
```

Copies whatever the job has produced so far — `clim/CCI_LAKES/`, `forcing/CCI_LAKES/`, and, if the portal already ran further steps, the generated namelist, model output and landgram figure under `output/<STA>__portal_<job_id>/` — and records `request.json`/`forcing_config.yaml`/`physiography_config.yaml` under `sites/provenance/<job_id>/`. Safe to re-run once the job progresses further; it skips files already staged unless `--force` is given. Add `--link` to symlink instead of copy.

*Expect (once the job finishes):* `clim/CCI_LAKES/surfclim_Ld-001_2017-2026.nc` + `surfinit_...`, `forcing/CCI_LAKES/met_era5HT_Ld-001_2017-2026.nc` (the tool hardcodes `era5` in this filename for every 1D run regardless of the class actually retrieved — see `../ecland-portal`'s README — so this is correct even though `forcing_source: oper` was requested), and an `output/Ld-001_2017-2026__portal_20260904T111326_Ld-001/` holding the portal's own run.

### 2. Run (or re-run with a different namelist)

The portal's own run is already a valid simulation (step 1's `output/..._portal_.../`). To try a namelist variant instead:

```bash
scripts/ecland_run_experiment.sh \
  -g CCI_LAKES \
  -t era5HT \
  -s Ld-001_2017-2026 \
  -n namelists/namelist_ecland_lake_ctl \
  -x <path_to_ecland_executable>
```

`-n` defaults to `namelists/namelist_ecland_lake_ctl` if omitted. Output lands in `output/Ld-001_2017-2026/` (no `__portal_...` suffix), keeping reruns distinct from the portal's own.

### 3. Post-process and benchmark

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
│   ├── stage_portal_job.sh      # import an ecland-portal job into this repo's layout
│   ├── ecland_run_experiment.sh # run one or more site experiments (vendored from plumber2-ecland)
│   ├── ecland_run_model.sh      # \_ vendored from plumber2-ecland, unmodified engine logic
│   ├── ecland_runtime.sh        # /
│   ├── ecland_create_namelist.py# /
│   ├── postproc_lake.py         # STUB: raw ecLand output -> lake variable schema
│   └── benchmark_lake.py        # STUB: score against ESA-CCI-Lakes observations
├── clim/CCI_LAKES/              # staged physiography/init (NetCDF) -- not in git
├── forcing/CCI_LAKES/           # staged forcing (NetCDF) -- not in git
├── obs/                         # ESA-CCI-Lakes observational product -- not sourced yet, not in git
├── output/                      # raw model output -- not in git
├── postprocessed/               # post-processed output -- not in git
└── benchmark/dashboards/        # metrics + dashboard per run -- checked in, once real
```

## Open work

- **Source the ESA-CCI-Lakes observational product.** Most likely the lake surface water temperature (LSWT) product; possibly also ice cover/duration. Nothing CCI-Lakes-shaped was found under `$PERM` while setting this repo up.
- **Implement `postproc_lake.py`** once a run has produced a real `o_lke.nc` to inspect — confirm FLake's output variable names against that file (or `yos_flake.F90` in the ecLand source) rather than guessing them ahead of time.
- **Implement `benchmark_lake.py`** once both of the above exist — likely following `plumber2-ecland/scripts/benchmark_plumber2.py`'s shape (per-site scores, self-contained HTML dashboard), scored per lake instead of per flux tower.
- **Add more lakes** to `sites/lakes.csv` as further ecland-portal jobs are run for them.

## License

Copyright 2026- ECMWF. Licensed under the [Apache Licence Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

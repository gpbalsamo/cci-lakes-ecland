#!/usr/bin/env python3
"""Point-extract ecLand forcing from ECFS's pre-archived daily 'oper' GRIB.

scripts/get_forcing_ecfs.sh stages raw daily global GRIB tarballs (10 files
per day: PSurf/Tair/Qair/Wind_E/Wind_N/SWdown/LWdown/Rainf/Snowf/Ctpf.grb --
already the exact final ecLand forcing variable set, not raw MARS parameters)
under forcing/raw/. This script reduces that to a single-point ecLand-ready
forcing NetCDF, reusing ../ecland/tools/create_forcing's own point-extraction
code (osm_pyutils/create_sites.py's create_forcing()) so the output schema
matches exactly what a fresh MARS-driven create_forcing run would produce --
same variable/attribute layout that scripts/ecland_create_namelist.py and the
model's NAMFORC reader already know how to consume.

WHAT THIS DOES NOT DO, DELIBERATELY: land-sea masking. The upstream tool's own
osm_pyutils/process_site_var.py always masks to the nearest LAND gridpoint
(lsm >= 0.5) before extraction -- wrong for a lake point, where the forcing
wanted is the one AT the location. ../ecland-portal's README documents this
exact "land-point trap" and patches around it for which_surface != land; this
script takes the same approach by simply never applying the mask, rather than
reproducing the patched copy.

Each daily archive spans a 25-hour window (a message valid at that day's
00:00, carried over from the previous day's 12Z run, through 24 hourly steps
to the next day's 00:00) -- see this script's own probing notes below, or just
`grib_ls -p dataDate,dataTime,step` on one of the .grb members. Consecutive
days therefore overlap by exactly one instant (each day's last message ==
the next day's first), so every day except the last requested one has its
final message dropped before concatenation.

'Rainf' needs one more fix, matching upstream's own special case: it is a
*derived* field (metview arithmetic over convective + large-scale precip)
that keeps the shortName of one of its inputs, 'cp', rather than 'tp'. Since
create_forcing() looks up the output variable name from the GRIB shortName,
this gets it reset to 'tp' before writing -- otherwise it would silently
collide with Ctpf, which legitimately carries shortName 'cp'.

GRIB messages concatenate at the byte level (each is self-delimited), so
per-day, per-variable fieldsets are cropped and (except the last day)
message-trimmed with metview, written to small GRIB files, and joined with
`cat` rather than metview's own '+' (which does field-by-field arithmetic,
not concatenation, and fails outright on mismatched message counts).

Usage:
  extract_point_forcing_ecfs.py --raw-dir DIR --start YYYYMMDD --end YYYYMMDD \
      --lat LAT --lon LON --out OUTPUT.nc [--work-dir DIR] [--keep-work-dir]

Needs the create_forcing extraction module set (ecmwf-toolbox, python3/new,
metview-python) -- NOT the model-run set; see ecland-portal's README on why
the two conflict. Also needs `cdo` for the final per-variable merge.

(C) Copyright 2026- ECMWF. Apache Licence Version 2.0.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import date, datetime, timedelta

import metview as mv

CREATE_FORCING_OSM_PYUTILS = os.environ.get(
    "CREATE_FORCING_OSM_PYUTILS",
    "/perm/pad/ecland/tools/create_forcing/scripts/osm_pyutils",
)
sys.path.insert(0, CREATE_FORCING_OSM_PYUTILS)
from create_sites import create_forcing  # noqa: E402  (path set above)

VARLIST = [
    "PSurf", "Tair", "Qair", "Wind_E", "Wind_N",
    "SWdown", "LWdown", "Rainf", "Snowf", "Ctpf",
]
RAW_PREFIX = "forcing_od_1_oper_1"


def parse_ymd(s: str) -> date:
    return datetime.strptime(s, "%Y%m%d").date()


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def extract_member(tar_path: str, var: str, dest_dir: str) -> str:
    with tarfile.open(tar_path, "r:gz") as tf:
        member = next(
            (m for m in tf.getmembers() if m.name.endswith(f"{var}.grb")), None
        )
        if member is None:
            raise FileNotFoundError(f"{var}.grb not found inside {tar_path}")
        tf.extract(member, path=dest_dir)
        return os.path.join(dest_dir, member.name)


def read_and_crop_with_retry(raw_member: str, area, attempts: int = 4, delay_s: float = 10.0):
    """mv.read(..., area=...) has been observed to fail intermittently with
    'Metview error: Retrieve-> Error code: 1' on an otherwise-valid input file
    -- a transient backend hiccup, not a data problem (retrying the identical
    call on the identical file succeeds). Retry with backoff rather than
    letting one bad moment kill an extraction spanning thousands of
    variable-days."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return mv.read(data=mv.read(raw_member), area=area)
        except Exception as exc:  # noqa: BLE001 -- metview raises plain Exception
            last_exc = exc
            print(f"   WARNING: mv.read/crop attempt {attempt}/{attempts} failed: {exc}", file=sys.stderr)
            if attempt < attempts:
                time.sleep(delay_s)
    raise last_exc


def build_variable_grib(var: str, days: list, raw_dir: str, work_dir: str, area) -> str:
    """Crop + day-boundary-trim + concatenate one variable across the whole
    date range into a single GRIB file. Returns its path.

    Resumable: a day whose cropped GRIB already exists in work_dir is reused
    rather than re-extracted, so a run interrupted partway through (or hitting
    the transient metview error above beyond its retry budget) can continue
    from where it left off by rerunning with the same --work-dir."""
    day_gribs = []
    for i, d in enumerate(days):
        dstr = d.strftime("%Y%m%d")
        day_grib = os.path.join(work_dir, f"{var}_{dstr}.crop.grb")
        if os.path.exists(day_grib):
            day_gribs.append(day_grib)
            continue
        tar_path = os.path.join(raw_dir, f"{RAW_PREFIX}_{dstr}.tar.gz")
        if not os.path.exists(tar_path):
            raise FileNotFoundError(f"missing {tar_path} -- has it been fetched yet?")
        raw_member = extract_member(tar_path, var, work_dir)
        fs = read_and_crop_with_retry(raw_member, area)
        os.remove(raw_member)
        is_last_day = i == len(days) - 1
        if not is_last_day:
            fs = fs[:-1]  # drop the instant duplicated by the next day's file
        mv.write(day_grib, fs)
        day_gribs.append(day_grib)

    combined = os.path.join(work_dir, f"{var}_combined.grb")
    with open(combined, "wb") as out:
        for g in day_gribs:
            with open(g, "rb") as src:
                shutil.copyfileobj(src, out)
            os.remove(g)
    return combined


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True, help="directory of forcing_od_1_oper_1_<YYYYMMDD>.tar.gz")
    ap.add_argument("--start", required=True, help="YYYYMMDD, inclusive")
    ap.add_argument("--end", required=True, help="YYYYMMDD, inclusive")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--out", required=True, help="output NetCDF path")
    ap.add_argument("--work-dir", default=None, help="default: a temp dir, removed afterward")
    ap.add_argument("--keep-work-dir", action="store_true")
    args = ap.parse_args()

    start, end = parse_ymd(args.start), parse_ymd(args.end)
    if end < start:
        sys.exit("ERROR: --end is before --start")
    days = list(daterange(start, end))
    area = [args.lat - 1.0, args.lon - 1.0, args.lat + 1.0, args.lon + 1.0]  # S,W,N,E

    work_dir = args.work_dir or tempfile.mkdtemp(prefix="extract_point_forcing_")
    os.makedirs(work_dir, exist_ok=True)
    print(f"=== extract_point_forcing_ecfs: {len(days)} days, {args.lat},{args.lon} ===")
    print(f"work dir: {work_dir}")

    try:
        per_var_nc = []
        for var in VARLIST:
            print(f"-- {var} --")
            combined_grib = build_variable_grib(var, days, args.raw_dir, work_dir, area)
            fs = mv.read(combined_grib)
            if var == "Rainf":
                short = mv.grib_get_string(fs, "shortName")[0]
                if short != "tp":
                    print(f"   Rainf shortName is '{short}', resetting to 'tp' (derived field, see docstring)")
                    fs = mv.grib_set(fs, ["shortName", "tp"])
            var_nc = os.path.join(work_dir, f"{var}.nc")
            create_forcing(fs, args.lat, args.lon, var_nc)
            per_var_nc.append(var_nc)
            print(f"   {len(fs)} timesteps -> {var_nc}")

        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        subprocess.run(
            ["cdo", "-O", "-f", "nc4", "-z", "zip_6", "merge", *per_var_nc, args.out],
            check=True,
        )
        print(f"=== wrote {args.out} ===")
    finally:
        if not args.keep_work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

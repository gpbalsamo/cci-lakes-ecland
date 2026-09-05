#!/usr/bin/env python3
"""Check spin-up convergence from an ecland_run_model.sh NLOOP run.

ecland_run_model.sh -l N repeats the same forcing period N times, each loop
restarting from the previous loop's end state (o_gg_S<n>.nc / restartout_S<n>.nc
for loops 1..N-1, o_gg.nc / restartout.nc unlabeled for the final loop N). This
reads the end-of-period FLake state from every loop and prints how it changes
loop over loop -- the standard "did spin-up converge" diagnostic.

Usage:
  check_spinup_convergence.py OUTPUT_DIR NLOOP

    OUTPUT_DIR  e.g. output/Ld-001_2017-2017 (holds o_gg_S1.nc .. o_gg.nc)
    NLOOP       number of loops the run was submitted with

(C) Copyright 2026- ECMWF. Apache Licence Version 2.0.
"""

import argparse
import os
import sys

import netCDF4 as nc

FIELDS = ["AvgSurfT", "TLMNW", "TLWML", "TLBOT", "HLML", "HLICE"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output_dir")
    ap.add_argument("nloop", type=int)
    args = ap.parse_args()

    rows = []
    for n in range(1, args.nloop + 1):
        path = os.path.join(args.output_dir, f"o_gg_S{n}.nc" if n < args.nloop else "o_gg.nc")
        if not os.path.exists(path):
            sys.exit(f"ERROR: missing {path} -- was this run submitted with -l {args.nloop}?")
        d = nc.Dataset(path)
        row = {f: float(d.variables[f][-1, 0, 0]) for f in FIELDS}
        row["ice_days"] = int((d.variables["HLICE"][:, 0, 0] > 0.001).sum())
        rows.append(row)

    header = f"{'loop':>4} " + " ".join(f"{f:>12}" for f in FIELDS) + f" {'ice_days':>9} {'max_delta':>10}"
    print(header)
    prev = None
    for n, row in enumerate(rows, start=1):
        line = f"{n:>4} " + " ".join(f"{row[f]:>12.4f}" for f in FIELDS) + f" {row['ice_days']:>9}"
        if prev is not None:
            delta = max(abs(row[f] - prev[f]) for f in FIELDS)
            line += f" {delta:>10.5f}"
        print(line)
        prev = row


if __name__ == "__main__":
    main()

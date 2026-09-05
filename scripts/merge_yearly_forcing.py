#!/usr/bin/env python3
"""Merge consecutive per-year ecLand forcing files into one multi-year file.

extract_point_forcing_ecfs.py, run once per calendar year (as
extract_point_forcing_ecfs.sbatch does for a range long enough to want
per-year jobs instead of one job for the whole span -- see that script's
comment for why), produces one file per year whose LAST timestep duplicates
the FIRST timestep of the following year's file (both are the Jan 1 00:00
boundary instant each year's extraction keeps so ecLand has what it needs to
drive the final hour of December -- see extract_point_forcing_ecfs.py's own
docstring on this). Concatenating the files as-is would therefore repeat
that instant once per year boundary. This drops it: keeps every record of
the first file, and every record except the first of each subsequent file.

Each file's `time` units are "seconds since <that year>-01-01 00:00:00", not
a shared origin, so timestamps are converted to a single continuous axis
(seconds since the first file's origin) via cftime rather than naively
concatenating the raw numbers.

Usage:
  merge_yearly_forcing.py YEAR_FILE [YEAR_FILE ...] --out OUTPUT.nc

    YEAR_FILE  in chronological order, e.g.
               met_ecfsHT_Ld-001_2017-2017.nc met_ecfsHT_Ld-001_2018-2018.nc ...

(C) Copyright 2026- ECMWF. Apache Licence Version 2.0.
"""

import argparse
import sys

import netCDF4 as nc
import numpy as np

SKIP_VARS = {"time", "lat", "lon"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("year_files", nargs="+", help="per-year forcing files, in chronological order")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    datasets = [nc.Dataset(f) for f in args.year_files]
    base_units = datasets[0].variables["time"].units

    all_times = []
    all_data = {v: [] for v in datasets[0].variables if v not in SKIP_VARS}

    for i, (path, d) in enumerate(zip(args.year_files, datasets)):
        t_var = d.variables["time"]
        dates = nc.num2date(t_var[:], t_var.units)
        t_abs = nc.date2num(dates, base_units)

        start = 0
        if i > 0:
            # Sanity check before dropping: this file's first instant must be
            # exactly the previous file's last, in both time and one variable.
            prev_last_t = all_times[-1][-1]
            if not np.isclose(t_abs[0], prev_last_t):
                sys.exit(f"ERROR: {path}'s first timestep does not follow "
                         f"{args.year_files[i-1]}'s last ({t_abs[0]} vs {prev_last_t}, "
                         f"both in '{base_units}') -- check the files are consecutive years.")
            probe_var = next(iter(all_data))
            prev_last_val = all_data[probe_var][-1][-1]
            this_first_val = d.variables[probe_var][0].flatten()[0]
            if not np.isclose(prev_last_val, this_first_val):
                sys.exit(f"ERROR: {path}'s first {probe_var} does not match "
                         f"{args.year_files[i-1]}'s last ({this_first_val} vs {prev_last_val}) "
                         "-- refusing to drop what looked like a duplicate boundary instant.")
            start = 1

        all_times.append(t_abs[start:])
        for v in all_data:
            all_data[v].append(d.variables[v][start:])

    merged_time = np.concatenate(all_times)
    if not np.all(np.diff(merged_time) == np.diff(merged_time)[0]):
        sys.exit("ERROR: merged time axis is not uniformly spaced -- a year boundary was "
                  "likely handled wrong. Refusing to write a forcing file ecLand would "
                  "silently misread.")

    with nc.Dataset(args.out, "w", format="NETCDF4") as out:
        d0 = datasets[0]
        out.createDimension("time", None)
        for dim in ("lat", "lon"):
            out.createDimension(dim, len(d0.dimensions[dim]))

        for dim in ("lat", "lon"):
            var = out.createVariable(dim, d0.variables[dim].dtype, (dim,))
            var[:] = d0.variables[dim][:]
            for attr in d0.variables[dim].ncattrs():
                var.setncattr(attr, d0.variables[dim].getncattr(attr))

        t_out = out.createVariable("time", d0.variables["time"].dtype, ("time",))
        t_out[:] = merged_time
        t_out.units = base_units
        for attr in d0.variables["time"].ncattrs():
            if attr != "units":
                t_out.setncattr(attr, d0.variables["time"].getncattr(attr))

        for v in all_data:
            src = d0.variables[v]
            var = out.createVariable(v, src.dtype, src.dimensions,
                                      zlib=True, complevel=6)
            var[:] = np.concatenate(all_data[v], axis=0)
            for attr in src.ncattrs():
                if attr not in ("_FillValue",):
                    var.setncattr(attr, src.getncattr(attr))

    print(f"=== wrote {args.out} ===")
    print(f"{len(merged_time)} timesteps, {base_units.replace('seconds since ', '')} "
          f"-> {merged_time[-1]/3600:.0f}h later")


if __name__ == "__main__":
    main()

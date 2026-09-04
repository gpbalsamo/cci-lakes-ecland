#!/usr/bin/env python3
"""Map raw ecLand output to a lake variable schema for benchmarking.

STATUS: stub. No ecLand run for a CCI lake has completed yet (Ladoga's
ecland-portal job is still in the forcing step -- see sites/lakes.csv), so
there is nothing to validate this against.

Modelled on plumber2-ecland/scripts/postproc_plumber2.py, which maps
output/<site>_<years>/o_*.nc to a fixed set of variables (Qle, Qh, NEE, ...)
against flux-tower observations. The lake analogue needs the FLake state
instead, from o_lke.nc (LWRLKE=.TRUE. in namelists/namelist_ecland_lake_ctl
turns this output on -- it is off in plumber2's control namelist):

  - lake surface (mixed-layer) temperature, to compare against ESA-CCI-Lakes
    lake surface water temperature (LSWT)
  - lake ice cover / thickness, if scoring ice phenology
  - mixed-layer depth, bottom temperature (FLake's other prognostics)

The exact o_lke variable names should be confirmed against the ecLand
build's src/surf/module/yos_flake.F90 (or the o_lke.nc actually produced by
the first completed run) before this is implemented -- do not guess field
names ahead of a real file to inspect.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputdir", required=True, help="e.g. output/")
    parser.add_argument("--outdir", required=True, help="e.g. postprocessed/")
    parser.parse_args()
    raise NotImplementedError(
        "postproc_lake.py is a stub -- implement once a completed run's "
        "o_lke.nc is available to inspect (see this file's docstring)."
    )


if __name__ == "__main__":
    main()

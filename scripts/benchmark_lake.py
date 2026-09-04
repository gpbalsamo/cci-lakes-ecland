#!/usr/bin/env python3
"""Score post-processed ecLand lake output against ESA-CCI-Lakes observations.

STATUS: stub. No ESA-CCI-Lakes observational product is available locally yet
(searched under $PERM for anything CCI-Lakes-shaped; found nothing). Sourcing
it -- most likely the CCI Lakes lake surface water temperature (LSWT) product,
possibly also ice cover/duration -- is a prerequisite for this script and is
not part of this initial scaffold.

Modelled on plumber2-ecland/scripts/benchmark_plumber2.py, which scores
against PLUMBER2's flux observations and renders a self-contained HTML
dashboard (scripts/dashboard_template.html) with bias/RMSE/R/NME, a site map
and a per-site drill-down. Once obs/ holds real CCI-Lakes data and
postproc_lake.py produces real per-lake output, this should follow the same
shape: one row per lake in sites/lakes.csv, one score per variable, one
dashboard under benchmark/dashboards/.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, help="e.g. postprocessed/")
    parser.add_argument("--obs-dir", required=True, help="e.g. obs/")
    parser.add_argument("--out-dir", required=True, help="e.g. benchmark/dashboards/<run-name>")
    parser.parse_args()
    raise NotImplementedError(
        "benchmark_lake.py is a stub -- needs a sourced ESA-CCI-Lakes "
        "observational product under obs/ and a working postproc_lake.py "
        "before this can score anything (see this file's docstring)."
    )


if __name__ == "__main__":
    main()

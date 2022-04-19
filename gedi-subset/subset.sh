#!/usr/bin/env bash

set -xeuo pipefail

basedir=$(dirname "$(readlink -f "$0")")

if type conda 1>/dev/null 2>&1; then
    runner="conda run --no-capture-output -n gedi_subset "
else
    runner=""
fi

subset_py="${runner}${basedir}/subset.py"

if test -d input; then
    # We are executing within a DPS job, so the AOI file was automatically
    # downloaded to the `input` directory.
    aoi=$(ls input/*)
    ${subset_py} --verbose --aoi "${aoi}" --limit "${1:-10000}"
else
    # This was invoked directly, so simply pass all arguments through to the
    # Python script.
    ${subset_py} --verbose "$@"
fi

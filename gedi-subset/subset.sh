#!/usr/bin/env bash

set -xuo pipefail

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

    n_actual=${#}
    n_expected=3

    if test ${n_actual} -gt 0 -a ${n_actual} -ne ${n_expected}; then
        echo "Expected ${n_expected} inputs, but got ${n_actual}:" $(printf " '%b'" "$@") >&2
        exit 1
    fi

    columns=$(test "${1:--}" != "-" && echo " --columns '${1:--}'")
    query=$(test "${2:--}" != "-" && echo " --query '${2:--}'")
    limit=$(test "${3:--}" != "-" && echo " --limit ${3:--}")
    ${subset_py} --verbose --aoi "${aoi}"${columns}${query}${limit}
else
    # This was invoked directly, so simply pass all arguments through to the
    # Python script.
    ${subset_py} --verbose "$@"
fi

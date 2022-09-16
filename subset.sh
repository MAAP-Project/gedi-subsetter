#!/usr/bin/env bash

set -xuo pipefail

basedir=$(dirname "$(readlink -f "$0")")
subset_py="conda run --no-capture-output -n gedi_subset ${basedir}/src/gedi_subset/subset.py"

if ! test -d "input"; then
    # There is no `input` sub-directory of the current working directory, so
    # simply pass all arguments through to the Python script.
    ${subset_py} --verbose "$@"
else
    # There is an `input` sub-directory of the current working directory, so
    # assume the AOI file is the sole file within the `input` sub-directory.
    aoi="$(ls input/*)"

    n_actual=${#}
    n_expected=4

    if test ${n_actual} -gt 0 -a ${n_actual} -ne ${n_expected}; then
        echo "Expected ${n_expected} inputs, but got ${n_actual}:$(printf " '%b'" "$@")" >&2
        exit 1
    fi

    options=()
    [[ "${1:--}" != "-" ]] && options=("${options[@]}" --doi "${1:--}")
    [[ "${2:--}" != "-" ]] && options=("${options[@]}" --columns "${2:--}")
    [[ "${3:--}" != "-" ]] && options=("${options[@]}" --query "${3:--}")
    [[ "${4:--}" != "-" ]] && options=("${options[@]}" --limit "${4:--}")

    ${subset_py} --verbose --aoi "${aoi}" "${options[@]}"
fi

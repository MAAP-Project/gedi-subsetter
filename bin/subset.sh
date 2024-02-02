#!/usr/bin/env bash

set -xeuo pipefail

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")
conda_env_prefix=$("${basedir}/bin/conda-prefix.sh")
conda_run=("conda" "run" "--no-capture-output" "--prefix" "${conda_env_prefix}")
subset_py="${basedir}/src/gedi_subset/subset.py"

if ! test -d "${basedir}/input"; then
    # There is no `input` sub-directory of the current working directory, so
    # simply pass all arguments through to the Python script.
    "${conda_run[@]}" "${subset_py}" --verbose "$@"
else
    # There is an `input` sub-directory of the current working directory, so
    # assume the AOI file is the sole file within the `input` sub-directory.
    aoi="$(ls input/*)"

    n_actual=${#}
    n_expected=9

    if test ${n_actual} -gt 0 -a ${n_actual} -ne ${n_expected}; then
        echo "Expected ${n_expected} inputs, but got ${n_actual}:$(printf " '%b'" "$@")" >&2
        exit 1
    fi

    options=()
    [[ "${1:--}" != "-" ]] && options=("${options[@]}" --doi "${1:--}")
    [[ "${2:--}" != "-" ]] && options=("${options[@]}" --temporal "${2:--}")
    [[ "${3:--}" != "-" ]] && options=("${options[@]}" --lat "${3:--}")
    [[ "${4:--}" != "-" ]] && options=("${options[@]}" --lon "${4:--}")
    [[ "${5:--}" != "-" ]] && options=("${options[@]}" --beams "${5:--}")
    [[ "${6:--}" != "-" ]] && options=("${options[@]}" --columns "${6:--}")
    [[ "${7:--}" != "-" ]] && options=("${options[@]}" --query "${7:--}")
    [[ "${8:--}" != "-" ]] && options=("${options[@]}" --limit "${8:--}")
    [[ "${9:--}" != "-" ]] && options=("${options[@]}" --output "${9:--}")

    ${subset_py} --verbose --aoi "${aoi}" "${options[@]}"
fi

#!/usr/bin/env bash

set -euo pipefail

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
base_dir=$(dirname "$(dirname "$(readlink -f "$0")")")

input_dir="${PWD}/input"
output_dir="${PWD}/output"
subset_py="${base_dir}/src/gedi_subset/subset.py"

if ! test -d "${input_dir}"; then
    # There is no `input` sub-directory of the current working directory, so
    # simply pass all arguments through to the Python script.  This is useful
    # for testing in a non-DPS environment, where there is no `input` directory
    # since the DPS system creates the `input` directory and places the AOI file
    # within it.
    command=("${subset_py}" --verbose "$@")
else
    # There is an `input` sub-directory of the current working directory, so
    # assume the AOI file is the sole file within the `input` sub-directory.
    aoi="$(ls "${input_dir}"/*)"

    n_actual=${#}
    n_expected=9

    if test ${n_actual} -lt ${n_expected} -o ${n_actual} -gt $((n_expected + 1)); then
        echo "Expected ${n_expected} inputs, but got ${n_actual}:$(printf " '%b'" "$@")" >&2
        exit 1
    fi

    args=(--verbose --aoi "${aoi}")
    args+=(--doi "${1}") # doi is required
    [[ "${2}" != "-" ]] && args+=(--temporal "${2}")
    args+=(--lat "${3}") # lat is required
    args+=(--lon "${4}") # lon is required
    [[ "${5}" != "-" ]] && args+=(--beams "${5}")
    args+=(--columns "${6}") # columns is required
    [[ "${7}" != "-" ]] && args+=(--query "${7}")
    [[ "${8}" != "-" ]] && args+=(--limit "${8}")
    [[ "${9}" != "-" ]] && args+=(--output "${9}")

    # If the last argument is not a hyphen, we expect it to be arguments to pass
    # to scalene for profiling our algorithm.
    if [[ "${10:--}" == "-" ]]; then
        command=("${subset_py}" "${args[@]}")
    else
        # Split the 10th argument into an array of arguments to pass to scalene.
        IFS=' ' read -ra scalene_args <<<"${10}"
        # Force output to be written to the output directory by adding the
        # `--outfile` argument after any user-provided arguments.  If the user
        # provides their own `--outfile` argument, it will be ignored.
        command=(
            scalene \
            "${scalene_args[@]}" \
            --web \
            --no-browser \
            --outfile "${output_dir}"/profile.html \
            "${subset_py}" --- "${args[@]}"
        )
    fi
fi

set -x
mkdir -p "${output_dir}"
conda_prefix=$("${base_dir}/bin/conda-prefix.sh")
conda run --no-capture-output --prefix "${conda_prefix}" "${command[@]}"

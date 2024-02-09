#!/usr/bin/env bash

set -euo pipefail

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
base_dir=$(dirname "$(dirname "$(readlink -f "$0")")")
input_dir="${base_dir}/input"
conda_prefix=$("${base_dir}/bin/conda-prefix.sh")
conda_run=("conda" "run" "--no-capture-output" "--prefix" "${conda_prefix}")
subset_py="${base_dir}/src/gedi_subset/subset.py"

echo "--- listing files in ${base_dir} ---"
ls "${base_dir}/*"
echo "---"

if ! test -d "${input_dir}"; then
    echo "No input directory found, assuming local development environment: ${input_dir}" >&2
    # There is no `input` sub-directory of the current working directory, so
    # simply pass all arguments through to the Python script.  This is useful
    # for testing in a non-DPS environment, where there is no `input` directory
    # since the DPS system creates the `input` directory and places the AOI file
    # within it.
    set -x
    "${conda_run[@]}" "${subset_py}" --verbose "$@"
else
    # There is an `input` sub-directory of the current working directory, so
    # assume the AOI file is the sole file within the `input` sub-directory.
    aoi="$(ls input/*)"

    n_actual=${#}
    n_expected=9

    if test ${n_actual} -lt ${n_expected} -o ${n_actual} -gt $((n_expected + 1)); then
        echo "Expected ${n_expected} inputs, but got ${n_actual}:$(printf " '%b'" "$@")" >&2
        exit 1
    fi

    inputs=()

    # Workaround for DPS bug where default input values must be quoted in order
    # for algorithm registration to work.  We strip surrounding quotes from all
    # arguments, either double or single quotes, if found.
    while ((${#})); do
        input=${1}

        # if [[ "${input}" =~ \".*\" ]]; then
        #     input=${1%\"}     # Strip leading quote
        #     input=${input#\"} # Strip trailing quote
        # elif [[ "${input}" =~ \'.*\' ]]; then
        #     input=${input%\'} # Strip leading quote
        #     input=${input#\'} # Strip trailing quote
        # fi

        inputs+=("${input}")
        shift
    done

    args=(--verbose --aoi "${aoi}")
    args+=(--doi "${inputs[0]}") # doi is required
    [[ "${inputs[1]}" != "-" ]] && args+=(--temporal "${inputs[1]}")
    args+=(--lat "${inputs[2]}") # lat is required
    args+=(--lon "${inputs[3]}") # lon is required
    [[ "${inputs[4]}" != "-" ]] && args+=(--beams "${inputs[4]}")
    args+=(--columns "${inputs[5]}") # columns is required
    [[ "${inputs[6]}" != "-" ]] && args+=(--query "${inputs[6]}")
    [[ "${inputs[7]}" != "-" ]] && args+=(--limit "${inputs[7]}")
    [[ "${inputs[8]}" != "-" ]] && args+=(--output "${inputs[8]}")

    if [[ "${inputs[9]:--}" != "-" ]]; then
        # The last argument is not a hyphen, so we expect it to be arguments to
        # pass to scalene for profiling our algorithm.
        IFS=' ' read -ra scalene_args <<<"${inputs[9]}"
        set -x
        "${conda_run[@]}" scalene "${scalene_args[@]}" --no-browser "${subset_py}" --- "${args[@]}"
    else
        set -x
        "${conda_run[@]}" "${subset_py}" "${args[@]}"
    fi
fi

#!/usr/bin/env bash

set -euo pipefail

bin=$(dirname "$(readlink -f "$0")")
base_dir=$(dirname "${bin}")
run="${bin}/run"

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
    echo "--- >>> ${input_dir} ---" >&2
    ls -l "${input_dir}" >&2
    echo "--- <<< ${input_dir} ---" >&2

    # There is an `input` sub-directory of the current working directory, so
    # assume the AOI file is the sole file within the `input` sub-directory.
    aoi="$(ls "${input_dir}"/*)"

    n_actual=${#}
    n_expected=12

    if test ${n_actual} -ne ${n_expected}; then
        echo "Expected ${n_expected} inputs, but got ${n_actual}:$(printf " '%b'" "$@")" >&2
        exit 1
    fi

    args=(--verbose --aoi "${aoi}")
    args+=(--doi "${1}")     # doi is required
    args+=(--lat "${2}")     # lat is required
    args+=(--lon "${3}")     # lon is required
    args+=(--columns "${4}") # columns is required
    [[ -n "${5}" ]] && args+=(--query "${5}")
    [[ -n "${6}" ]] && args+=(--temporal "${6}")
    [[ -n "${7}" ]] && args+=(--beams "${7}")
    [[ -n "${8}" ]] && args+=(--limit "${8}")
    [[ -n "${9}" ]] && args+=(--output "${9}")
    [[ -n "${10}" ]] && args+=(--s3fs-open-kwargs "${10}")
    [[ -n "${11}" ]] && args+=(--processes "${11}")
    # Split the last argument into an array of arguments to pass to scalene.
    IFS=' ' read -ra scalene_args <<<"${12}"

    command=("${subset_py}" "${args[@]}")

    if [[ ${#scalene_args[@]} -ne 0 ]]; then
        ext="html"

        for arg in "${scalene_args[@]}"; do
            if [[ "${arg}" == "--json" ]]; then
                ext="json"
            elif [[ "${arg}" == "--cli" ]]; then
                ext="txt"
            fi
        done

        # Force output to be written to the output directory by adding the
        # `--outfile` argument after any user-provided arguments.  If the user
        # provides their own `--outfile` argument, it will be ignored.  Also,
        # add `--no-browser` to ensure that scalene does not attempt to open a
        # browser.
        command=(
            scalene
            "${scalene_args[@]}"
            --no-browser
            --outfile "${output_dir}/profile.${ext}"
            ---
            "${command[@]}"
        )
    fi
fi

set -x
mkdir -p "${output_dir}"

# Capture stderr and write to a log file in the current working directory so
# that if the job fails, the log file is copied to the triage directory (all
# "${PWD}/*.log" files are copied to the triage directory by the DPS system).
# Note that we chose to capture stderr rather than configuring Python logging
# to write directly to a file because it is a tricky feat to coordinate logging
# from multiple processes into a single file.
logfile="${PWD}/gedi-subset.log"

"${run}" "${command[@]}" 2>"${logfile}"

# If we get here, the command above succeeded (otherwise this script would have
# exited with a non-zero status).  We can now move the log file to the output
# directory so that is included in the final output directory for the user.
mv "${logfile}" "${output_dir}"

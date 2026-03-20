#!/usr/bin/env bash

# Run the GEDI Subsetter
#
# This script is invoked by the DPS system and does the following:
#
# - Parses arguments, handling either positional-only or keyword-only args.
# - Invokes the gedi-subset command via "pixi run" in the pixi production
#   environment.

set -euo pipefail

output_dir="${PWD}/output"
base_dir=$(dirname "$(dirname "$(readlink -f "$0")")")

function normalize_args() {
    case "${1}" in
        --*)
            normalize_keyword_args "$@"
            ;;
        *)
            if ! raw_kwargs=$(positional_to_keyword_args "$@"); then
                exit $?
            fi

            readarray -t kwargs <<< "${raw_kwargs}"
            normalize_keyword_args "${kwargs[@]}"
            ;;
    esac
}

function normalize_keyword_args() {
    subset_args=()
    scalene_arg=""

    while [[ ${#} -gt 0 ]]; do
        case "${1}" in
            --output)
                # We need to handle --output specially because we need to prefix
                # the specified output file with the output directory, which the
                # user is not expected to supply.  We assume a value was given,
                # but it can be an empty string.
                subset_args+=("${1}" "${output_dir}/${2}")
                shift 2
                ;;
            --scalene)
                # We assume a value was given, but it can be an empty string.
                scalene_arg="${2}"
                shift 2
                ;;
            *)
                # Otherwise, just collect each argument as-is.
                subset_args+=("${1}")
                shift 1
                ;;
        esac
    done

    echo "${scalene_arg}"

    for arg in "${subset_args[@]}"; do
        echo "${arg}"
    done
}

function positional_to_keyword_args() {
    n_actual=${#}
    n_expected=13

    if test ${n_actual} -ne ${n_expected}; then
        echo "Expected ${n_expected} inputs, but got ${n_actual}:$(printf " '%b'" "$@")" >&2
        exit 1
    fi

    # AOI is a "file" input that the DPS automatically downloads to the input
    # directory, and is not supplied as an explicit command-line argument.

    input_dir="${PWD}/input"

    if [[ ! -d "${input_dir}" ]]; then
        echo "Input directory does not exist: ${input_dir}" >&2
        exit 1
    fi

    aoi=$(ls "${input_dir}"/* 2>/dev/null)

    if [[ -z "${aoi}" ]]; then
        echo "Input directory is empty (no AOI file found): ${input_dir}" >&2
        exit 1
    fi

    kwargs=(--aoi "${aoi}")

    kwargs+=(--doi "${1}")     # doi is required
    kwargs+=(--lat "${2}")     # lat is required
    kwargs+=(--lon "${3}")     # lon is required
    kwargs+=(--columns "${4}") # columns is required
    [[ -n "${5}" ]] && kwargs+=(--query "${5}")
    [[ -n "${6}" ]] && kwargs+=(--temporal "${6}")
    [[ -n "${7}" ]] && kwargs+=(--beams "${7}")
    [[ -n "${8}" ]] && kwargs+=(--limit "${8}")
    kwargs+=(--output "${9}")  # output is required
    [[ -n "${10}" ]] && kwargs+=(--tolerated-failure-percentage "${10}")
    [[ -n "${11}" ]] && kwargs+=(--fsspec-kwargs "${11}")
    [[ -n "${12}" ]] && kwargs+=(--processes "${12}")
    [[ -n "${13}" ]] && kwargs+=(--scalene "${13}")

    for kwarg in "${kwargs[@]}"; do
        echo "${kwarg}"
    done
}

function parse_scalene_arg() {
    local scalene_arg

    # The first argument is a string of scalene arguments joined into a single,
    # space-separated string that we have to split into separate arguments.
    # For example, we need to split "arg1 ... argN" into ("arg1" ... "argN").
    scalene_arg=$1
    ext="html"

    # Split joined scalene arguments into array of arguments to pass to scalene.
    readrray -t scalene_args <<< "${scalene_arg}"

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
    scalene_args+=(--no-browser --outfile "${output_dir}/profile.${ext}")

    for arg in "${scalene_args[@]}"; do
        echo "${arg}"
    done
}

function build_command() {
    args=("$@")
    scalene_arg=${args[0]}
    subset_args=("${args[@]:1}")

    if [[ -z "${scalene_arg}" ]]; then
        echo gedi-subset
    else
        if ! raw_scalene_args=$(parse_scalene_arg "${scalene_arg}"); then
            exit $?
        fi

        readarray -t scalene_args <<< "${raw_scalene_args}"

        echo scalene

        for arg in "${scalene_args[@]}"; do
            echo "${arg}"
        done

        # Scalene doesn't recognize the installed gedi-subset command, because
        # it expects to be able to locate the file on the file system, so we
        # have to specify the python file directly.
        echo src/gedi_subset/subset.py
        echo ---
    fi

    for arg in "${subset_args[@]}"; do
        echo "${arg}"
    done
}

function run_command() {
    set -x

    mkdir -p "${output_dir}"

    pixi run \
        --quiet \
        --no-progress \
        --no-install \
        --frozen \
        --environment prod \
        --manifest-path "${base_dir}/pyproject.toml" \
        -- "$@"
}

function main() {
    args=("$@")

    if ! normalized_args=$(normalize_args "$@"); then
        exit $?
    fi

    readarray -t args <<< "${normalized_args}"

    if ! raw_command=$(build_command "${args[@]}"); then
        exit $?
    fi

    readarray -t command <<< "${raw_command}"

    run_command "${command[@]}"
}

main "$@"

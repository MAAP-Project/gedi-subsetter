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
    case "${1:-}" in
        --*)
            normalize_keyword_args "$@"
            ;;
        *)
            raw_kwargs=$(positional_to_keyword_args "$@") || exit $?
            readarray -t kwargs <<< "${raw_kwargs}"
            normalize_keyword_args "${kwargs[@]}"
            ;;
    esac
}

function normalize_keyword_args() {
    subset_args=()

    while [[ ${#} -gt 0 ]]; do
        case "${1}" in
            --output)
                # We need to handle --output specially because we need to prefix
                # the specified output file with the output directory, which the
                # user is not expected to supply.  We assume a value was given,
                # but it can be an empty string.
                subset_args+=("${1}" "${output_dir}/${2:-}")
                shift 2
                ;;
            *)
                # Otherwise, just collect each argument as-is.
                subset_args+=("${1}")
                shift 1
                ;;
        esac
    done

    for arg in "${subset_args[@]}"; do
        echo "${arg}"
    done
}

function positional_to_keyword_args() {
    n_actual=${#}
    n_expected=12

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

    for kwarg in "${kwargs[@]}"; do
        echo "${kwarg}"
    done
}

function build_command() {
    args=("$@")

    echo gedi-subset

    for arg in "${args[@]}"; do
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

    normalized_args=$(normalize_args "$@") || exit $?
    readarray -t args <<< "${normalized_args}"

    raw_command=$(build_command "${args[@]}") || exit $?
    readarray -t command <<< "${raw_command}"

    run_command "${command[@]}"
}

main "$@"

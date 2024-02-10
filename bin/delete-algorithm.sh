#!/usr/bin/env bash

function stderr() {
    echo >&2 "${1}"
}

yes=

while ((${#})); do
    case "${1}" in
    -y | --yes)
        yes=1
        ;;
    *)
        stderr "ERROR: unrecognized argument: ${1}"
        exit 1
        ;;
    esac
    shift
done

# Obtain the algorithm name and version from the algorithm_config.yaml file, but
# use the current branch name as the version if the current branch is not `main`.

yaml_file=${1:-algorithm_config.yaml}
branch=$(git rev-parse --abbrev-ref HEAD)
algorithm_name=$(grep "^algorithm_name:" "${yaml_file}" | sed -E 's/algorithm_name: ([^[:space:]]+).*/\1/')
algorithm_version=$(grep "^algorithm_version:" "${yaml_file}" | sed -E 's/algorithm_version: ([^[:space:]]+).*/\1/')
[[ "${branch}" != "main" ]] && algorithm_version=${branch}
algorithm_id="${algorithm_name}:${algorithm_version}"

if [[ -z "${yes}" ]]; then
    read -rp "Are you sure you want to delete algorithm '${algorithm_id}'? [yes/NO] "

    if [[ ! "${REPLY}" =~ ^[Yy][Ee][Ss]$ ]]; then
        stderr "Aborted."
        exit 1
    fi
fi

stderr "Deleting algorithm '${algorithm_id}'..."

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")

conda_prefix=$("${basedir}/bin/conda-prefix.sh")

message=$(conda run --no-capture-output --prefix "${conda_prefix}" python -c "
from maap.maap import MAAP

maap = MAAP('api.maap-project.org')

if not (r := maap.deleteAlgorithm('${algorithm_id}')):
    print(r.json()['message'])
")

echo "${message}"
[[ -z "${message}" ]] || exit 1

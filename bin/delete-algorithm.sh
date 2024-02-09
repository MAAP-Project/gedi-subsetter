#!/usr/bin/env bash

yaml_file=${1:-algorithm_config.yaml}
tag=$(git tag --points-at HEAD)
branch=$(git rev-parse --abbrev-ref HEAD)
name=$(grep "^algorithm_name:" "${yaml_file}" | sed -E 's/algorithm_name: ([^[:space:]]+).*/\1/')
version=$(grep "^algorithm_version:" "${yaml_file}" | sed -E 's/algorithm_version: ([^[:space:]]+).*/\1/')

function stderr() {
    echo >&2 "${1}"
}

if [[ "${branch}" != "main" ]]; then
    version=${branch//\//-}
elif [[ -z "${tag}" ]]; then
    stderr "ERROR: You're on the main branch, but there's no tag for the current commit."
    stderr "Please follow the instructions for creating a new release in CONTRIBUTING.md."
    exit 1
elif [[ "${tag}" != "${version}" ]]; then
    stderr "ERROR: The tag for the current commit is '${tag}', but the version in algorithm_config.yaml is '${version}'."
    stderr "Please follow the instructions for creating a new release in CONTRIBUTING.md."
    exit 1
fi

# TODO: add confirmation prompt!

algorithm_id="${name}:${version}"
stderr "Deleting algorithm version '${algorithm_id}'..."

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")
conda_prefix=$("${basedir}/bin/conda-prefix.sh")
conda_run=("conda" "run" "--no-capture-output" "--prefix" "${conda_prefix}")

"${conda_run[@]}" python -c "
import json
import sys
import tempfile

import yaml
from maap.maap import MAAP

maap = MAAP('api.maap-project.org')

try:
    r = maap.deleteAlgorithm('${algorithm_id}')
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
"

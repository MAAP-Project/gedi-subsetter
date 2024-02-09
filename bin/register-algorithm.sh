#!/usr/bin/env bash

yaml_file=${1:-algorithm_config.yaml}
tag=$(git tag --points-at HEAD)
branch=$(git rev-parse --abbrev-ref HEAD)
algorithm_name=$(grep "^algorithm_name:" "${yaml_file}" | sed -E 's/algorithm_name: ([^[:space:]]+).*/\1/')
algorithm_version=$(grep "^algorithm_version:" "${yaml_file}" | sed -E 's/algorithm_version: ([^[:space:]]+).*/\1/')

function stderr() {
    echo 1>&2 "${1}"
}

if [[ "${branch}" =~ "/" ]]; then
    # Slashes in branch names are not acceptable because the DPS system uses the
    # branch name as part of the Docker image tag (which cannot contain slashes).
    stderr "ERROR: Branch names cannot contain slashes. Please rename the branch and try again."
    exit 1
elif [[ "${branch}" != "main" ]]; then
    algorithm_version=${branch}
elif [[ -z "${tag}" ]]; then
    stderr "ERROR: You're on the main branch, but there's no tag for the current commit."
    stderr "Please follow the instructions for creating a new release in CONTRIBUTING.md."
    exit 1
elif [[ "${tag}" != "${algorithm_version}" ]]; then
    stderr "ERROR: The tag for the current commit is '${tag}', but the version in algorithm_config.yaml is '${algorithm_version}'."
    stderr "Please follow the instructions for creating a new release in CONTRIBUTING.md."
    exit 1
fi

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")

algorithm_id="${algorithm_name}:${algorithm_version}"
stderr "Registering algorithm '${algorithm_id}' (${yaml_file})..."

if [[ $("${basedir}/bin/describe-algorithm.sh" 2>&1 >/dev/null) ]]; then
    stderr ""
    stderr "ERROR: Algorithm '${algorithm_id}' already exists."
    stderr ""
    stderr "If you want to re-register the algorithm, you must first delete it:"
    stderr ""
    stderr "    bin/delete-algorithm.sh"
    stderr ""
    exit 1
fi

conda_prefix=$("${basedir}/bin/conda-prefix.sh")
conda_run=("conda" "run" "--no-capture-output" "--prefix" "${conda_prefix}")

"${conda_run[@]}" python -c "
import json
import sys
import tempfile

import yaml
from maap.maap import MAAP

maap = MAAP('api.maap-project.org')

with open('${yaml_file}') as f:
    config = yaml.safe_load(f)

with tempfile.NamedTemporaryFile('w+') as f:
    config['algorithm_version'] = '${algorithm_version}'
    json.dump(config, f, indent=2)
    f.seek(0)

    try:
        r = maap.register_algorithm_from_yaml_file(f.name)
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
"

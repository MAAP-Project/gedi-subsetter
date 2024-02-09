#!/usr/bin/env bash

function stderr() {
    echo 1>&2 "${1}"
}

yes=

while ((${#})); do
    case "${1}" in
    -y | --yes)
        yes=${1}
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
tag=$(git tag --points-at HEAD)
branch=$(git rev-parse --abbrev-ref HEAD)
algorithm_name=$(grep "^algorithm_name:" "${yaml_file}" | sed -E 's/algorithm_name: ([^[:space:]]+).*/\1/')
algorithm_version=$(grep "^algorithm_version:" "${yaml_file}" | sed -E 's/algorithm_version: ([^[:space:]]+).*/\1/')
[[ "${branch}" != "main" ]] && algorithm_version=${branch}
algorithm_id="${algorithm_name}:${algorithm_version}"

if [[ "${algorithm_version}" =~ "/" ]]; then
    # Slashes in branch names are not acceptable because the DPS system uses the
    # branch name as part of the Docker image tag (which cannot contain slashes).
    stderr "ERROR: Branch names cannot contain slashes. Please rename the branch and try again."
    exit 1
fi

if [[ "${branch}" == "main" ]]; then
    if [[ -z "${tag}" ]]; then
        stderr "ERROR: You're on the main branch, but there's no tag for the current commit."
        stderr "Please follow the instructions for creating a new release in CONTRIBUTING.md."
        exit 1
    elif [[ "${tag}" != "${algorithm_version}" ]]; then
        stderr "ERROR: The tag for the current commit is '${tag}', but the version in algorithm_config.yaml is '${algorithm_version}'."
        stderr "Please follow the instructions for creating a new release in CONTRIBUTING.md."
        exit 1
    fi
fi

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")

# If the algorithm already exists, delete it first.
if [[ $("${basedir}/bin/describe-algorithm.sh") ]]; then
    stderr "Algorithm '${algorithm_id}' already exists, so it must be deleted first."
    # ${yes} is intentionally unquoted to allow it to be empty.
    # shellcheck disable=SC2086
    "${basedir}/bin/delete-algorithm.sh" ${yes}
    [[ $? ]] && exit 1
fi

stderr "Registering algorithm '${algorithm_id}' (${yaml_file})..."
conda_prefix=$("${basedir}/bin/conda-prefix.sh")

conda run --no-capture-output --prefix "${conda_prefix}" python -c "
import json
import sys
import tempfile

import yaml
from maap.maap import MAAP

maap = MAAP('api.maap-project.org')

with open('${yaml_file}') as f:
    algorithm_config = yaml.safe_load(f)

with tempfile.NamedTemporaryFile('w+') as f:
    # Replace the algorithm version, write the modified config to a temporary
    # file, then rewind the file pointer to the beginning so it can be read for
    # registration.
    algorithm_config['algorithm_version'] = '${algorithm_version}'
    json.dump(algorithm_config, f, indent=2)
    f.seek(0)

    try:
        r = maap.register_algorithm_from_yaml_file(f.name)
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
"

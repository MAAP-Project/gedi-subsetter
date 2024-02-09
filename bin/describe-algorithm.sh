#!/usr/bin/env bash

function stderr() {
    echo >&2 "${1}"
}

# Obtain the algorithm name and version from the algorithm_config.yaml file, but
# use the current branch name as the version if the current branch is not `main`.

yaml_file=${1:-algorithm_config.yaml}
branch=$(git rev-parse --abbrev-ref HEAD)
algorithm_name=$(grep "^algorithm_name:" "${yaml_file}" | sed -E 's/algorithm_name: ([^[:space:]]+).*/\1/')
algorithm_version=$(grep "^algorithm_version:" "${yaml_file}" | sed -E 's/algorithm_version: ([^[:space:]]+).*/\1/')
[[ "${branch}" != "main" ]] && algorithm_version=${branch}
algorithm_id="${algorithm_name}:${algorithm_version}"

# Apply dirname twice to get to the top of the repo, since this script is in the
# `bin` directory (i.e., first dirname gets to `bin`, second gets to the top).
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")

conda_prefix=$("${basedir}/bin/conda-prefix.sh")

conda run --no-capture-output --prefix "${conda_prefix}" python -c "
import json
import sys
import tempfile

import yaml
from maap.maap import MAAP

maap = MAAP('api.maap-project.org')

if r := maap.describeAlgorithm('${algorithm_id}'):
    # This response is XML, not JSON, unfortunately, so the output is not
    # convenient to read.
    print(r.text)
else:
    print(r.text, file=sys.stderr)
    sys.exit(1)
"

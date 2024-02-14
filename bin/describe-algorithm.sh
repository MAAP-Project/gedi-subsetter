#!/usr/bin/env bash

# Describes the version of the algorithm that is currently checked out.  If the
# current branch is not `main`, uses the current branch name as the version.
# Otherwise, uses the version from the `algorithm_config.yaml` file, if and only
# if the current commit is tagged with that version:
#
#     describe-algorithm.sh
#
# Currently, this script only prints the XML response from the MAAP API, which
# is not very useful.  It would be better to parse the XML and print a more
# human-readable description of the algorithm.  For now, this script is used
# mainly for other scripts to check whether or not the algorithm exists.

set -euo pipefail

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

conda_prefix=$("${basedir}/bin/conda-prefix.py")

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

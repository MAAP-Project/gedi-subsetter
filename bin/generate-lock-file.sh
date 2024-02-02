#!/usr/bin/env bash

set -euo pipefail

# Apply dirname twice to get the parent directory of the directory containing
# this script.
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")

set -x

conda lock --mamba -f "${basedir}/environment.yml" -f "${basedir}/environment-dev.yml"

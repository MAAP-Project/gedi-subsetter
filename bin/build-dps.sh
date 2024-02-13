#!/usr/bin/env bash

# Builds the gedi_subset conda environment from a conda lock file, specifically
# for the DPS system.  This script is intended to be specified as the algorithm
# configuration's `build_command` because that configuration value does not
# accept any arguments.  This script is a wrapper around the `build.sh` script
# using specific options that are appropriate for the DPS system.

set -euo pipefail

basedir=$(dirname "$(readlink -f "$0")")

time "${basedir}/build.sh" --yes --no-dev

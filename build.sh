#!/usr/bin/env bash

set -xeuo pipefail

basedir=$(dirname "$(readlink -f "$0")")

# Execute subdirectories' build scripts
for subdir in "${basedir}"/*/; do
    build_script=${subdir}build.sh

    if [ -f "${build_script}" ]; then
        bash "${build_script}"
    fi
done

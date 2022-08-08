#!/usr/bin/env bash

basedir=$(dirname "$(readlink -f "$0")")

set -xeuo pipefail

# Make sure conda is updated to a version that supports the --no-capture-output option
conda install -y -n base -c conda-forge "conda>=4.13.0"

# Execute subdirectories' build scripts
for subdir in $(ls -d */)
do
    file=${basedir}/${subdir}build.sh
    if [ -f "$file" ]; then
        bash $file
    fi
done

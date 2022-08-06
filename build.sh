#!/usr/bin/env bash

export basedir=$(dirname "$(readlink -f "$0")")

set -xeuo pipefail

# Make sure conda is up to date
conda update -y -n base -c conda-forge conda

# Install dependencies from lock file for speed and reproducibility
case $(uname) in
Linux)
    platform="linux"
    ;;
Darwin)
    platform="osx"
    ;;
*)
    echo >&2 "Unsupported platform: $(uname)"
    exit 1
    ;;
esac
export platform

# Execute subdirectories' build scripts
for subdir in $(ls -d */)
do
    file=${basedir}/${subdir}build.sh
    if [ -f "$file" ]; then
        bash $file
    fi
done
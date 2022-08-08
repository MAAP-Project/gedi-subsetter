#!/usr/bin/env bash

set -xeuo pipefail

basedir=$(dirname "$(readlink -f "$0")")

# Execute subdirectories' build scripts
for subdir in $(ls -d */)
do
    file=${basedir}/${subdir}build.sh
    if [ -f "$file" ]; then
        bash $file
    fi
done

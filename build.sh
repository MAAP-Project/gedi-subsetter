#!/usr/bin/env bash

basedir=$(dirname "$(readlink -f "$0")")

set -xeuo pipefail

# Execute subdirectories' build scripts
for subdir in $(ls -d */)
do
    file=${basedir}/${subdir}build.sh
    if [ -f "$file" ]; then
        bash $file
    fi
done

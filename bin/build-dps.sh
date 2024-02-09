#!/usr/bin/env bash

set -euo pipefail

basedir=$(dirname "$(readlink -f "$0")")

time "${basedir}/build.sh" --yes --no-dev

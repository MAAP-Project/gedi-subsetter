#!/usr/bin/env bash

set -euo pipefail

basedir=$(dirname "$(readlink -f "$0")")

"${basedir}/build.sh" --yes --no-dev

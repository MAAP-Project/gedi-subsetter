#!/usr/bin/env bash

basedir=$(dirname "$(readlink -f "$0")")

set -xeuo pipefail

mamba env create -f "${basedir}/environment.yml"

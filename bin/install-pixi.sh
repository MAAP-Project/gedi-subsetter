#!/usr/bin/env bash

set -eou pipefail

CONDA_BIN_DIR=/opt/conda/bin

if type -p pixi >/dev/null; then
    echo "pixi is already installed on the PATH" >&2
elif ! test -d "${CONDA_BIN_DIR}"; then
    echo "${CONDA_BIN_DIR} directory not found; not installing pixi" >&2
    exit 1
else
    # Install pixi in the same directory where conda is installed because it is
    # already on the PATH.
    wget -q -O- https://pixi.sh/install.sh | PIXI_BIN_DIR="${CONDA_BIN_DIR}" PIXI_NO_PATH_UPDATE=1 bash
fi

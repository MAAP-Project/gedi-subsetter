#!/usr/bin/env bash

set -eou pipefail

this_dir=$(dirname "$(readlink -f "$0")")
base_dir=$(dirname "${this_dir}")

"${this_dir}/install-pixi.sh"
"${this_dir}/install-subsetter.sh"

manifest_path=(--manifest-path "${base_dir}/pyproject.toml")

# Clean up things we don't need in production to trim the resulting image size.
pixi clean cache --yes
pixi clean "${manifest_path[@]}" --environment default

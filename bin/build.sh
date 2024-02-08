#!/usr/bin/env bash

set -euo pipefail

function usage() {
    echo 1>&2 "Usage: $0 [OPTIONS]"
    echo 1>&2 ""
    echo 1>&2 "Build the gedi_subset conda environment from a conda lock file."
    echo 1>&2 ""
    echo 1>&2 "Options:"
    echo 1>&2 "  -h, --help  Show this help message and exit"
    echo 1>&2 "  -y, --yes   Sets any confirmation values to 'yes' automatically."
    echo 1>&2 "              Users will not be asked to confirm installation of"
    echo 1>&2 "              conda-lock within the conda base environment."
    echo 1>&2 ""
    echo 1>&2 "All options not listed above will be passed to 'conda lock install'."
    echo 1>&2 "See https://conda.github.io/conda-lock/cli/gen/#conda-lock-install."
}

# Apply dirname twice to get the parent directory of the directory containing
# this script.
basedir=$(dirname "$(dirname "$(readlink -f "$0")")")

conda_env=()
conda_base_deps=("conda~=23.0")
conda_lock_dep="conda-lock~=2.0"
conda_lock_args=()
yes=

while ((${#})); do
    case "${1}" in
    -h | --help)
        usage
        exit 0
        ;;
    -y | --yes)
        yes=1
        shift
        ;;
    -n | --name)
        conda_env=("--name" "${2}")
        shift 2
        ;;
    --name=?*)
        conda_env=("${1}")
        shift
        ;;
    -p | --prefix)
        conda_env=("--prefix" "${2}")
        shift 2
        ;;
    --prefix=?*)
        conda_env=("${1}")
        shift
        ;;
    *)
        conda_lock_args+=("${1}")
        shift
        ;;
    esac
done

# If no environment name or prefix was provided, use the default name.
if [[ "${#conda_env[@]}" == "0" ]]; then
    conda_env=("--name" "gedi_subset")
fi

conda_lock_args+=("${conda_env[@]}")

if [[ ! $(type conda-lock 2>/dev/null) ]]; then
    if [[ -n "${yes}" ]]; then
        conda_base_deps+=("${conda_lock_dep}")
    else
        read -r -p "NOTE: conda-lock is not installed

If you wish to install conda-lock yourself, answer 'no' to the following
question, and see installation options at https://github.com/conda/conda-lock.

Would you like to install conda-lock into your conda base environment? [y/N] " yn
        case "${yn}" in
        [Yy]*)
            conda_base_deps+=("${conda_lock_dep}")
            echo
            echo "Installing conda-lock into conda base environment."
            echo
            ;;
        *)
            exit 0
            ;;
        esac
    fi
fi

if [[ ! $(type conda 2>/dev/null) ]]; then
    echo "ERROR: conda was not found.  Make sure conda is installed.  If conda is" >&2
    echo "installed, this may be due to conda's base environment being shadowed by" >&2
    echo "some other active environment.  Run 'conda activate base' and try again." >&2
    exit 1
fi

set -x

# Install conda 'base' environment dependencies.
conda install --yes --solver libmamba --name base --channel conda-forge "${conda_base_deps[@]}"

# Install dependencies from the conda lock file for speed and reproducibility.
# Since there is at least one package (maap-py) that is not available on conda,
# we need to use pip to install it (conda does this for us), so we must set
# PIP_REQUIRE_VENV=0 to avoid complaints about installing packages outside of a
# virtual environment.
PIP_REQUIRE_VENV=0 conda lock install "${conda_lock_args[@]}" "${basedir}/conda-lock.yml"

# pip install gedi-subsetter in editable mode.
PIP_REQUIRE_VENV=0 conda run --no-capture-output "${conda_env[@]}" \
    python -m pip install -e "${basedir}" --no-deps

# Fail build if finicky mix of fiona and gdal isn't correct, so that we don't
# have to wait to execute a DPS job to find out.
conda run --no-capture-output "${conda_env[@]}" python -c '
import geopandas as gpd
import tempfile
import warnings
from shapely.geometry import Point

# Make sure pip install worked
from maap.maap import MAAP
# Make sure MAAP can be instantiated
maap = MAAP()

warnings.filterwarnings("ignore", message=".*initial implementation of Parquet.*")

d = {"col1": ["name1", "name2"], "geometry": [Point(1, 2), Point(2, 1)]}
gdf = gpd.GeoDataFrame(d, crs="EPSG:4326")

with tempfile.TemporaryFile() as fp:
    gdf.to_parquet(fp)
    assert gdf.equals(gpd.read_parquet(fp))
'

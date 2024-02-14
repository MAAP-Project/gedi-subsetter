#!/usr/bin/env python

# NOTE: Not intended for direct use.  This is used by other scripts.

# Finds the conda environment prefix for the gedi_subset environment, whether it
# was created in the default conda env location, or via an explicit prefix, and
# prints it to stdout.  If the environment is not found, or multiple are found,
# an error message is printed to stderr and the script exits with a non-zero
# status code.
#
# If the environment variable GEDI_SUBSET_CONDA_PREFIX is set, it is used as the
# prefix, rather than searching the list of conda envs, but it is not checked
# for existence.

import json
import os
import subprocess
import sys

if prefix := os.getenv("GEDI_SUBSET_CONDA_PREFIX"):
    print(prefix)
    sys.exit(0)

proc = subprocess.run(["conda", "env", "list", "--json"], capture_output=True)

if proc.returncode:
    print(proc.stderr.decode("utf-8"), file=sys.stderr)
    sys.exit(1)

envs = json.loads(proc.stdout)["envs"]
prefixes = tuple(env for env in envs if env.endswith("/gedi_subset"))

if not prefixes:
    print(
        " ".join(
            [
                "ERROR: Could not find the gedi_subset conda environment.  If",
                "you have not created the environment, run bin/build.sh.  If",
                "you have already created it, but used a different name, set",
                "the GEDI_SUBSET_CONDA_PREFIX environment variable to the",
                "absolute path of the environment.",
            ]
        ),
        file=sys.stderr,
    )
    sys.exit(1)

if len(prefixes) > 1:
    print(
        " ".join(
            [
                "ERROR: Found multiple conda environments named gedi_subset:",
                f"{prefixes}.  Please remove all but one, or set the",
                "GEDI_SUBSET_CONDA_PREFIX environment variable to the full",
                "path of the desired environment.",
            ]
        ),
        file=sys.stderr,
    )
    sys.exit(1)

print(prefixes[0])

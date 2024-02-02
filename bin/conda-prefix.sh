#!/usr/bin/env bash

python -c "
import json
import os
import sys

prefix = os.getenv('GEDI_SUBSET_CONDA_PREFIX')

if prefix:
    print(prefix)
    sys.exit(0)

envs = json.loads('''$(conda env list --json)''')['envs']
prefixes = tuple(env for env in envs if env.endswith('/gedi_subset'))

if len(prefixes) == 0:
    print(
        ' '.join(
            [
                'ERROR: Could not find the gedi_subset conda environment.  If',
                'you have not created the environment, run bin/build.sh.  If',
                'you have already created it, but used a different name, set',
                'the GEDI_SUBSET_CONDA_PREFIX environment variable to the',
                'absolute path of the environment.'
            ]
        ),
        file=sys.stderr,
    )
    sys.exit(1)

if len(prefixes) > 1:
    print(
        ' '.join(
            [
                'ERROR: Found multiple conda environments named gedi_subset:',
                f'{prefixes}.  Please remove all but one, or set the',
                'GEDI_SUBSET_CONDA_PREFIX environment variable to the full',
                'path of the desired environment.',
            ]
        ),
        file=sys.stderr,
    )
    sys.exit(1)

print(prefixes[0])
"

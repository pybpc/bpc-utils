#!/bin/bash
set -Eeuxo pipefail

if [ ! -f setup.py ]; then
    echo 'Please execute this script in the project root directory.'
    exit 1
fi

flake8
./ci/pylint.sh
mypy . || true  # TODO: enforce mypy later
bandit -r .
vermin --backport typing -q -t=3.4- .

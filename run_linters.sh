#!/bin/bash
set -Eeuxo pipefail
flake8
./pylint.sh
bandit -r .
vermin -q -t=3.4- .

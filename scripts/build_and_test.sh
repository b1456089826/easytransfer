#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install -e .
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 scripts/e2e_demo.py --workdir "./out/e2e-demo"

python3 -m pip install build
python3 -m build

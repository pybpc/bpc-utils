import itertools
import os
import pathlib
import subprocess  # nosec
import sys
from typing import List

if not os.path.isfile('setup.py'):
    sys.exit('Please execute this script in the project root directory.')

# pylint: disable=line-too-long
pylint_args = [
    '--load-plugins=pylint.extensions.emptystring,pylint.extensions.comparetozero,pylint.extensions.docstyle,pylint.extensions.check_elif,pylint.extensions.redefined_variable_type,pylint.extensions.overlapping_exceptions,pylint.extensions.docparams,pylint.extensions.empty_comment,pylint.extensions.typing',
    '--enable=all',
    '--disable=I,disallowed-name,invalid-name,missing-class-docstring,missing-function-docstring,missing-module-docstring,design,too-many-lines,eq-without-hash,old-division,no-absolute-import,input-builtin,too-many-nested-blocks,spelling',
    '--max-line-length=120',
    '--init-import=yes',
]  # type: List[str]
# pylint: enable=line-too-long

current_dir = pathlib.Path('.')
py_files = sorted(map(str, itertools.chain(
    current_dir.glob('./**/*.py'),
    current_dir.glob('./**/*.pyw'),
    current_dir.glob('./**/*.py3'),
    current_dir.glob('./**/*.pyi'),
)))

sys.exit(subprocess.call(['pylint'] + pylint_args + ['--'] + py_files))  # nosec

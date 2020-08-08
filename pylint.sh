#!/bin/bash
set -Eeuxo pipefail
shopt -s dotglob globstar nullglob
pylint --load-plugins=pylint.extensions.check_elif,pylint.extensions.docstyle,pylint.extensions.emptystring,pylint.extensions.overlapping_exceptions \
       --disable=all \
       --enable=F,E,W,R,basic,classes,format,imports,refactoring,else_if_used,docstyle,compare-to-empty-string,overlapping-except \
       --disable=blacklisted-name,invalid-name,missing-class-docstring,missing-function-docstring,missing-module-docstring,design,too-many-lines,eq-without-hash,old-division,no-absolute-import,input-builtin,too-many-nested-blocks \
       --max-line-length=120 \
       --init-import=yes \
       ./**/*.py ./**/*.pyw ./**/*.py3 ./**/*.pyi

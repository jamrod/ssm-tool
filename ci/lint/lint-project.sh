#!/bin/bash
# Lint python files in the entire projects, see .pylintrc and setup.cfg for configuration
out_file=ci/lint/output/lint-output.txt
echo Linting run $(date) > $out_file
files=$(find . -name \*.py -not -path "__pycache__" -not -path "*/cdk.out/*" -not -path "*/scratch/*")
printf "\npycodestyle output ------------------------------------\n" >> $out_file
pycodestyle $files >> $out_file
prgm1=$?
printf "\npylint output -----------------------------------------\n" >> $out_file
pylint $files >> $out_file
prgm2=$?
echo files checked ----------------------------------------- >> $out_file
for item in ${files[@]}; do echo $item; done >> $out_file
echo $prgm1 $prgm2
check=$(($prgm1 + $prgm2))
if (($check > 0)) ; then echo problems detected, check lint-output.txt; exit 1; fi

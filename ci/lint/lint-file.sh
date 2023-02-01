#!/bin/bash
# Use this to lint an individual file
FILE=$1
out_file=ci/lint/output/file-lint-output.txt
pycodestyle --ignore=E501,W503 $FILE \
> $out_file
prgm1=$?
pylint --disable=logging-format-interpolation,useless-super-delegation,duplicate-code,logging-fstring-interpolation,line-too-long,import-error,too-many-public-methods,consider-using-dict-items \
$FILE \
>> $out_file
prgm2=$?
echo $prgm1 $prgm2
check=$(($prgm1 + $prgm2))
if (($check > 0)) ; then
    echo problems detected, check $out_file
    cat $out_file
fi

#!/bin/bash
stage=$1
[ -z $1 ] && stage=dev

echo running synth on SsmParameterToolStack-${stage^} ...
cdk synth SsmParameterToolStack-${stage^} -c stage=${stage}

[[ $? -gt 0 ]] || echo Complete!
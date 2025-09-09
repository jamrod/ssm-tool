#!/bin/bash
# Runs cdk synth for specified stage and stack
declare -A STACKS=(  \
  [parameter]=SsmParameterToolStack \
  [layer]=SsmSharedLayerStack \
  [run-document]=SsmRunDocumentStack \
  [deploy-document]=SsmDeployDocumentStack \
)
ERR_MSG="Missing parameter(s), 'build.sh stage stack' stages = DEV PRD; stacks = ${!STACKS[@]}"

if [[ "dev DEV Dev" =~ $1 ]]; then
    stage=DEV
    elif [[ "prod PROD Prod prd PRD Prd" =~ $1 ]]; then
        stage=PRD
    else
        echo $ERR_MSG && exit 1
fi

shift
stack=$1
if [[ ! ${!STACKS[@]} =~ ${stack} ]]; then  # if the stack is not declared as a key in the associative array STACKS
    echo $ERR_MSG && exit 1
fi

echo running synth on ${STACKS[$stack]} $stage
cdk synth ${STACKS[$stack]} -e -c stage=${stage}
[[ $? -gt 0 ]] && exit 1 || echo Complete!

#!/bin/bash
# run sam local invoke to test lambdas
stack=$1
stage=$2

# get stack name from simple name
declare -A NAME_MAP=( [ssm_parameter_tool]="SsmParameterToolStack" )
printf -v stack_name ${NAME_MAP["$stack"]}

# create env file
python ci/test/make_env.py ${stack} ${stage}

# run sam local invoke on the stack, make sure event file exists and is accurate
aws-runas devinator sam local invoke \
    -t cdk.out/${stack_name}-${stage^}.template.json \
    -e ci/test/events/${stack}.json \
    -n ci/test/envs/${stack}-${stage}.json \

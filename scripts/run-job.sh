#!/bin/bash
# Run this to run ssm tool jobs, runas govinator for prod
declare -i pollDelay=60 # delay in seconds between polling execution status
declare -i maxPoll=10 # max number of times to poll before exiting
declare -i exit_code=0
for job in jobs/parameter_tool/*.json; do
    printf "running job ${job}\n waiting...\n"
    # outfile=$(f=${job#jobs/}; echo outputs/${f%.json}-result.json) # declare output file by stripping 'jobs/' from the front and swapping '.json' for '-result.json' at the end
    exec_arn=$({
        aws stepfunctions start-execution --state-machine-arn arn:aws:states:us-east-1:530786275774:stateMachine:pcm_ssm_parameter_tool_SM \
            --input "$(jq -R . ${job} --raw-output)" \
            --output json
        }| jq .executionArn)
    echo Got Execution Arn : ${exec_arn}
    declare -i polls=0
    while true; do
        sleep ${pollDelay}
        status=$(aws stepfunctions describe-execution --execution-arn ${exec_arn//'"'/} | jq .status)
        if [[ ${status} != '"RUNNING"' ]]; then
        echo Status : ${status}
        break;
        fi
        polls=$(( $polls +1 ))
        if [[ $polls -ge $maxPoll ]]; then
            echo Max polls of ${maxPoll} exceeded
            exit 1
        fi
        echo Poll ${polls}, Job In Progress...
    done
done

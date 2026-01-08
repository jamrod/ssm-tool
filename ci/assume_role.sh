#!/bin/bash
ROLE_ARN=${ROLE_ARN:=$1}
set -e
echo $ROLE_ARN
eval "$(aws sts assume-role --role-arn "${ROLE_ARN}" --duration-seconds 3600 --role-session-name "CI-$(date +%Y%m%d)-${RANDOM}" | jq -r '.Credentials|@sh "aws_secret=\(.SecretAccessKey) aws_session=\(.SessionToken) expiration=\(.Expiration) aws_key=\(.AccessKeyId)"')"
export AWS_ACCESS_KEY_ID=${aws_key} && echo AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID >> $GITHUB_ENV
export AWS_SECRET_ACCESS_KEY=${aws_secret} && echo AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY >> $GITHUB_ENV
export AWS_SESSION_TOKEN=${aws_session} >/dev/null && echo AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN >> $GITHUB_ENV

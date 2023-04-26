#!/bin/bash

ENVMNT=$1

if [[ ${ENVMNT} == "prod" ]]
  then
    BUCKET=pcm-shared-code-747207162522
  else
    BUCKET=pcm-shared-code-530786275774
fi

echo "sync ./documents with s3://${BUCKET}/ssm_tool/ssm_documents/"
aws s3 sync ./documents s3://${BUCKET}/ssm_tool/ssm_documents/

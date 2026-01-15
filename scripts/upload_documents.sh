#!/bin/bash

ENVMNT=$1

if [[ ${ENVMNT} == "PRD" ]]
  then
    BUCKET=my-bucket-1
    BUCKET=my-bucket-2
fi

echo "sync ./documents with s3://${BUCKET}/ssm_tool/ssm_documents/"
aws s3 sync ./documents s3://${BUCKET}/ssm_tool/ssm_documents/

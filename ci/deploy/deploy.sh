#!/bin/bash
if [ -z $1 ] || [ ${1} == 'dev' ]
    then
      stage=dev
      role=devinator
  elif [ ${1} == 'prod' ]
    then
      stage=${1}
      role=govinator
  else
    echo invalid argument $1 try dev or prod
fi

if [[ $? -gt 0 ]]; then
  exit 1
fi

echo deploying stack SsmParameterToolStack-${stage^} ...
aws-runas $role cdk deploy --app 'cdk.out/' SsmParameterToolStack-${stage^} -t t_AppID=SVC02522 --require-approval never
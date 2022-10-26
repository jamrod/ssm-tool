#!/bin/bash
if [ -z $1 ] || [ ${1^} == 'Dev' ]
    then
      stage=Dev
      role=devinator
  elif [ ${1^} == 'Prod' ]
    then
      stage=Prod
      role=govinator
  else
    echo invalid argument $1 try dev or prod

echo running synth on SsmCleanerStack-${stage} ...
cdk synth SsmCleanerStack-${stage}

echo deploying stack SsmCleanerStack-${stage} ...
aws-runas $role cdk deploy --app 'cdk.out/' SsmCleanerStack-${stage} -t t_AppID=SVC02522
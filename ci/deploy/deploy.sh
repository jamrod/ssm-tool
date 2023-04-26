#!/bin/bash
if [ ${1} == 'dev' ]
    then
      stage=dev
      role=devinator
  elif [ ${1} == 'prod' ]
    then
      stage=prod
      role=govinator
  else
    echo invalid argument $1 try dev or prod
    exit 1
fi
stack=$2
if [ -z ${stack} ]; then
  echo 'Missing parameter(s), deploy.sh dev layer|parameter|run-document|deploy-document'
  exit 1
fi
echo Running deploy on ${stage} ${stack}
case $stack in
parameter)
  aws-runas ${role} cdk deploy --app 'cdk.out/' SsmParameterToolStack-${stage^} --require-approval never -c stage=${stage}
;;
layer)
  aws-runas ${role} cdk deploy --app 'cdk.out/' SsmSharedLayerStack-${stage^} --require-approval never -c stage=${stage}
;;
run-document)
  aws-runas ${role} cdk deploy --app 'cdk.out/' SsmRunDocumentStack-${stage^} --require-approval never -c stage=${stage}
;;
deploy-document)
  aws-runas ${role} cdk deploy --app 'cdk.out/' SsmDeployDocumentStack-${stage^} --require-approval never -c stage=${stage}
;;
esac

[[ $? -gt 0 ]] || echo Complete!

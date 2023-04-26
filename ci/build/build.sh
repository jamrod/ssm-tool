#!/bin/bash
#!/bin/bash
stage=$1
stack=$2
if [[ -z ${stack} ]]; then
    echo 'Missing parameter(s), build.sh dev layer|parameter|run-document|deploy-document'
    exit 1
fi
echo running synth on $stack ${stage^}
case $stack in
parameter)
    cdk synth SsmParameterToolStack-${stage^} -c stage=${stage}
    ;;
layer)
    cdk synth SsmSharedLayerStack-${stage^} -c stage=${stage}
    ;;
run-document)
    cdk synth SsmRunDocumentStack-${stage^} -c stage=${stage}
    ;;
deploy-document)
    cdk synth SsmDeployDocumentStack-${stage^} -c stage=${stage}
    ;;
*)
    echo invalid argument $stack, try: layer, parameter, document
    exit 1
    ;;
esac

[[ $? -gt 0 ]] || echo Complete!

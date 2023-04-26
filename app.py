"""Entrypoint for cdk ssm_tool"""
import json
from aws_cdk import App, Environment, Tags

from infrastructure.ssm_parameter_tool_stack import SsmParameterToolStack
from infrastructure.ssm_shared_layer import SsmSharedLayerStack
from infrastructure.ssm_run_document_stack import SsmRunDocumentStack
from infrastructure.ssm_deploy_document_stack import SsmDeployDocumentStack

with open(file="stage_parameters.json", mode="r", encoding="utf=8") as read_file:
    parameters = json.load(fp=read_file)

app = App()

stage_name = app.node.try_get_context("stage")

assert stage_name in (
    "dev",
    "prod",
), "You must specify either -c stage=dev or -c stage=prod following cdk synth|deploy"


SsmParameterToolStack(
    app,
    f"SsmParameterToolStack-{stage_name.capitalize()}",
    env=Environment(
        account=parameters["environment"][stage_name]["account"],
        region=parameters["environment"][stage_name]["region"],
    ),
    stage_params=parameters["ssm_parameter_tool"][stage_name],
)

SsmRunDocumentStack(
    app,
    f"SsmRunDocumentStack-{stage_name.capitalize()}",
    env=Environment(
        account=parameters["environment"][stage_name]["account"],
        region=parameters["environment"][stage_name]["region"],
    ),
    stage_params=parameters["ssm_run_document_tool"][stage_name],
)

SsmDeployDocumentStack(
    app,
    f"SsmDeployDocumentStack-{stage_name.capitalize()}",
    env=Environment(
        account=parameters["environment"][stage_name]["account"],
        region=parameters["environment"][stage_name]["region"],
    ),
    stage_params=parameters["ssm_deploy_document_tool"][stage_name],
)

SsmSharedLayerStack(
    app,
    f"SsmSharedLayerStack-{stage_name.capitalize()}",
    env=Environment(
        account=parameters["environment"][stage_name]["account"],
        region=parameters["environment"][stage_name]["region"],
    ),
)

Tags.of(app).add("t_AppID", "SVC02522")
Tags.of(app).add("t_environment", stage_name.upper())
Tags.of(app).add("t_dcl", "1")

app.synth()

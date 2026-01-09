"""Entrypoint for cdk ssm_tool
change here to trigger deploy pipeline
"""
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
    "DEV",
    "PRD",
), "You must specify either -c stage=DEV or -c stage=PRD following cdk synth|deploy"


SsmParameterToolStack(
    app,
    construct_id="SsmParameterToolStack",
    env=Environment(**parameters["environment"][stage_name]),
    stage_params=parameters["ssm_parameter_tool"][stage_name],
)

SsmRunDocumentStack(
    app,
    construct_id="SsmRunDocumentStack",
    env=Environment(**parameters["environment"][stage_name]),
    stage_params=parameters["ssm_run_document_tool"][stage_name],
)

SsmDeployDocumentStack(
    app,
    construct_id="SsmDeployDocumentStack",
    env=Environment(**parameters["environment"][stage_name]),
    stage_params=parameters["ssm_deploy_document_tool"][stage_name],
)

SsmSharedLayerStack(
    app,
    construct_id="SsmSharedLayerStack",
    env=Environment(**parameters["environment"][stage_name]),
)

Tags.of(app).add("t_AppID", "SVC02522")
Tags.of(app).add("t_environment", stage_name)
Tags.of(app).add("t_dcl", "1")

app.synth()

"""Entrypoint for cdk ssm_tool"""
import json
from aws_cdk import App, Environment

from infrastructure.ssm_parameter_tool_stack import SsmParameterToolStack

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


app.synth()

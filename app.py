"""Entrypoint for cdk ssm_cleaner stack"""
from aws_cdk import App, Environment

from infrastructure.ssm_cleaner_stack import SsmCleanerStack
from stage_parameters import parameters

app = App()

dev = Environment(account="119377359737", region="us-east-1")
prod = Environment(account="056952386373", region="us-east-1")


SsmCleanerStack(app, "SsmCleanerStack-Dev", env=dev, stage_params=parameters.get("dev"))
SsmCleanerStack(app, "SsmCleanerStack-Prod", env=dev, stage_params=parameters.get("prod"))

app.synth()

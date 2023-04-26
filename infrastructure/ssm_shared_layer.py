"""cdk representation of the SSM Tool shared layer stack"""
# pylint: disable=W0612,R0903
from aws_cdk import aws_lambda as lambda_, App, RemovalPolicy, Stack, aws_ssm
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion


class SsmSharedLayerStack(Stack):
    """Creates a shared layer for use in the SSM Tool cdk stacks"""

    def __init__(self, app: App, id_: str, env: dict) -> None:
        super().__init__(app, id_)
        self.env = env

        # Create layer
        ssm_tool_shared_layer = PythonLayerVersion(
            self,
            "ssm_tool_shared_layer",
            entry="layers/utilities",
            description="Shared utilities",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Record version arn as ssm parameter
        aws_ssm.StringParameter(
            self,
            "version_arn",
            parameter_name="pcm_ssm_tool_shared_layer",
            string_value=ssm_tool_shared_layer.layer_version_arn,
        )

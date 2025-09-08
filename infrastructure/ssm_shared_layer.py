"""cdk representation of the SSM Tool shared layer stack"""
# pylint: disable=W0612,R0903
from aws_cdk import aws_lambda, RemovalPolicy, Stack, aws_ssm
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
from constructs import Construct


class SsmSharedLayerStack(Stack):
    """Creates a shared layer for use in the SSM Tool cdk stacks"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create layer
        ssm_tool_shared_layer = PythonLayerVersion(
            self,
            "ssm_tool_shared_layer",
            entry="layers/utilities",
            description="Shared utilities",
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_11, aws_lambda.Runtime.PYTHON_3_13],
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Record version arn as ssm parameter
        aws_ssm.StringParameter(
            self,
            "version_arn",
            parameter_name="pcm_ssm_tool_shared_layer",
            string_value=ssm_tool_shared_layer.layer_version_arn,
        )

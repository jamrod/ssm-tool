"""cdk representation of the ssm_deploy_document_tool stack"""
# pylint: disable=W0612,R0903,R0914
from aws_cdk import (
    Duration,
    Stack,
    aws_ssm,
    aws_iam,
    aws_lambda,
    aws_stepfunctions,
    aws_stepfunctions_tasks,
)
from constructs import Construct


class SsmDeployDocumentStack(Stack):
    """Entrypoint to the SSM deploy Document application which creates and shares documents"""

    def __init__(self, scope: Construct, construct_id: str, stage_params: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.stage_params = stage_params

        # Get layer
        ssm_tool_shared_layer_arn = aws_ssm.StringParameter.value_for_string_parameter(
            self, "pcm_ssm_tool_shared_layer"
        )
        ssm_tool_shared_layer = aws_lambda.LayerVersion.from_layer_version_arn(
            self, "ssm_tool_shared_layer", ssm_tool_shared_layer_arn
        )

        # iam role
        pcm_ssm_deploy_document_tool_role = aws_iam.Role(
            self,
            "ssm_deploy_document_tool_role",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="pcm_ssm_deploy_document_tool_role",
        )
        pcm_ssm_deploy_document_tool_role.add_to_policy(
            aws_iam.PolicyStatement(resources=["*"], actions=["sts:AssumeRole"])
        )
        pcm_ssm_deploy_document_tool_role.add_managed_policy(
            aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # lambda function
        ssm_deploy_document_tool_lambda = aws_lambda.Function(
            self,
            "ssm_deploy_document_tool_lambda",
            code=aws_lambda.Code.from_asset("lambdas/ssm_deploy_document_tool"),
            runtime=aws_lambda.Runtime.PYTHON_3_13,
            handler="ssm_deploy_document_tool.lambda_handler",
            environment=self.stage_params,
            timeout=Duration.minutes(15),
            layers=[ssm_tool_shared_layer],
            role=pcm_ssm_deploy_document_tool_role,
            memory_size=512,
            function_name="pcm_ssm_deploy_document_tool",
        )

        # step function tasks
        init_step = aws_stepfunctions_tasks.LambdaInvoke(
            self,
            "init",
            lambda_function=ssm_deploy_document_tool_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )
        deploy = aws_stepfunctions_tasks.LambdaInvoke(
            self,
            "deploy_step",
            lambda_function=ssm_deploy_document_tool_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=1, interval=Duration.seconds(60)
        )
        error_check_step = aws_stepfunctions_tasks.LambdaInvoke(
            self,
            "error_check_step",
            lambda_function=ssm_deploy_document_tool_lambda,
            payload=aws_stepfunctions.TaskInput.from_object({"action": "error_check"}),
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )

        # map steps
        deploy_map = aws_stepfunctions.Map(
            self,
            "deploy_map",
        ).iterator(deploy)

        # state_machine
        state_machine_ssm_deploy_document_tool = aws_stepfunctions.StateMachine(
            self,
            "state_machine",
            state_machine_name="pcm_ssm_deploy_document_tool_SM",
            definition_body=aws_stepfunctions.DefinitionBody.from_chainable(
                init_step
                .next(deploy_map)
                .next(error_check_step),
            )
        )

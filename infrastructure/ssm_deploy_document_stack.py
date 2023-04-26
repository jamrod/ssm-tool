"""cdk representation of the ssm_deploy_document_tool stack"""
# pylint: disable=W0612,R0903,R0914
from aws_cdk import (
    App,
    Stack,
    Duration,
    aws_ssm,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_stepfunctions as step_functions,
    aws_stepfunctions_tasks as sf_tasks,
)


class SsmDeployDocumentStack(Stack):
    """Entrypoint to the SSM deploy Document application which creates and shares documents"""

    def __init__(self, app: App, id_: str, env: dict, stage_params: dict) -> None:
        super().__init__(app, id_)
        self.stage_params = stage_params
        self.env = env

        # Get layer
        ssm_tool_shared_layer_arn = aws_ssm.StringParameter.value_for_string_parameter(
            self, "pcm_ssm_tool_shared_layer"
        )
        ssm_tool_shared_layer = lambda_.LayerVersion.from_layer_version_arn(
            self, "ssm_tool_shared_layer", ssm_tool_shared_layer_arn
        )

        # iam role
        pcm_ssm_deploy_document_tool_role = iam.Role(
            self,
            "ssm_deploy_document_tool_role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="pcm_ssm_deploy_document_tool_role",
        )
        pcm_ssm_deploy_document_tool_role.add_to_policy(
            iam.PolicyStatement(resources=["*"], actions=["sts:AssumeRole"])
        )
        pcm_ssm_deploy_document_tool_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # lambda function
        ssm_deploy_document_tool_lambda = lambda_.Function(
            self,
            "ssm_deploy_document_tool_lambda",
            code=lambda_.Code.from_asset("lambdas/ssm_deploy_document_tool"),
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="ssm_deploy_document_tool.lambda_handler",
            environment=self.stage_params,
            timeout=Duration.minutes(15),
            layers=[ssm_tool_shared_layer],
            role=pcm_ssm_deploy_document_tool_role,
            memory_size=512,
            function_name="pcm_ssm_deploy_document_tool",
        )

        # step function tasks
        init_step = sf_tasks.LambdaInvoke(
            self,
            "init",
            lambda_function=ssm_deploy_document_tool_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )
        deploy = sf_tasks.LambdaInvoke(
            self,
            "deploy_step",
            lambda_function=ssm_deploy_document_tool_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=1, interval=Duration.seconds(60)
        )
        error_check_step = sf_tasks.LambdaInvoke(
            self,
            "error_check_step",
            lambda_function=ssm_deploy_document_tool_lambda,
            payload=step_functions.TaskInput.from_object({"action": "error_check"}),
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )

        # map steps
        deploy_map = step_functions.Map(
            self,
            "deploy_map",
        ).iterator(deploy)

        # state_machine
        state_machine_ssm_deploy_document_tool = step_functions.StateMachine(
            self,
            "state_machine",
            state_machine_name="pcm_ssm_deploy_document_tool_SM",
            definition=step_functions.Chain.start(init_step)
            .next(deploy_map)
            .next(error_check_step),
        )

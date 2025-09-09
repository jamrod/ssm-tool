"""cdk representation of the ssm_run_document stack"""
# pylint: disable=W0612,R0903,R0914
from aws_cdk import (
    Stack,
    Duration,
    aws_ssm,
    aws_iam,
    aws_lambda,
    aws_stepfunctions,
    aws_stepfunctions_tasks,
)
from constructs import Construct


class SsmRunDocumentStack(Stack):
    """Entrypoint to the SSM Run Document application which will run an SSM Document on a variety of intances across regions and accounts"""

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
        ssm_run_document_role = aws_iam.Role(
            self,
            "ssm_run_document_role",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="pcm_ssm_run_document_role",
        )
        ssm_run_document_role.add_to_policy(
            aws_iam.PolicyStatement(resources=["*"], actions=["sts:AssumeRole"])
        )
        ssm_run_document_role.add_managed_policy(
            aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # lambda function
        ssm_run_document_lambda = aws_lambda.Function(
            self,
            "ssm_run_document_lambda",
            code=aws_lambda.Code.from_asset("lambdas/ssm_run_document"),
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            handler="ssm_run_document.lambda_handler",
            environment=self.stage_params,
            timeout=Duration.minutes(15),
            layers=[ssm_tool_shared_layer],
            role=ssm_run_document_role,
            memory_size=512,
            function_name="pcm_ssm_run_document_lambda",
        )

        # step function tasks
        init_step = aws_stepfunctions_tasks.LambdaInvoke(
            self,
            "init",
            lambda_function=ssm_run_document_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )
        divide_jobs_step = aws_stepfunctions_tasks.LambdaInvoke(
            self,
            "divide_jobs",
            lambda_function=ssm_run_document_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )
        run_job_step = aws_stepfunctions_tasks.LambdaInvoke(
            self,
            "run_job",
            lambda_function=ssm_run_document_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=1, interval=Duration.seconds(60)
        )
        error_check_step = aws_stepfunctions_tasks.LambdaInvoke(
            self,
            "error_check_step",
            lambda_function=ssm_run_document_lambda,
            payload=aws_stepfunctions.TaskInput.from_object({"action": "error_check"}),
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )

        # map steps
        divide_jobs_map = aws_stepfunctions.Map(
            self,
            "divide_jobs_map",
        ).iterator(divide_jobs_step)
        run_jobs_map = aws_stepfunctions.Map(
            self,
            "run_jobs_map",
        ).iterator(run_job_step)
        handle_jobs_map = aws_stepfunctions.Map(
            self, "handle_jobs_map", output_path="$[0]"
        ).iterator(run_jobs_map)

        # state_machine
        state_machine_ssm_run_document = aws_stepfunctions.StateMachine(
            self,
            "state_machine",
            state_machine_name="pcm_ssm_run_document_SM",
            definition=aws_stepfunctions.Chain.start(init_step)
            .next(divide_jobs_map)
            .next(handle_jobs_map)
            .next(error_check_step),
        )

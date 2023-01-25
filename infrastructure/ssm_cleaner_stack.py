"""cdk representation of the ssm-cleaner stack"""
# pylint: disable=W0612,R0903,R0914
from aws_cdk import (
    App,
    Stack,
    Duration,
    RemovalPolicy,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_stepfunctions as step_functions,
    aws_stepfunctions_tasks as sf_tasks,
)
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion


class SsmCleanerStack(Stack):
    """Entrypoint to the SSM Cleaner application which cleans up ssm parameters"""

    def __init__(self, app: App, id_: str, env: dict, stage_params: dict) -> None:
        super().__init__(app, id_)
        self.stage_params = stage_params
        self.env = env

        # Create layer
        ssm_cleaner_layer = PythonLayerVersion(
            self,
            "ssm_cleaner_layer",
            entry="layers/utilities",
            description="Shared utilities",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            removal_policy=RemovalPolicy.RETAIN,
        )

        # iam role
        ssmcleaner_stack_role = iam.Role(
            self,
            "publish_stack_role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        ssmcleaner_stack_role.add_to_policy(
            iam.PolicyStatement(resources=["*"], actions=["sts:AssumeRole"])
        )
        ssmcleaner_stack_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # lambda function
        ssmcleaner_lambda = lambda_.Function(
            self,
            "ssm_cleaner_lambda",
            code=lambda_.Code.from_asset("lambdas/ssm_parameter_cleaner"),
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="ssm_parameter_cleaner.lambda_handler",
            environment=self.stage_params,
            timeout=Duration.minutes(15),
            layers=[ssm_cleaner_layer],
            role=ssmcleaner_stack_role,
            memory_size=512,
            function_name="pcm_ssm_tool"
        )

        # step function tasks
        init_step = sf_tasks.LambdaInvoke(
            self,
            "init",
            lambda_function=ssmcleaner_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )
        divide_jobs_step = sf_tasks.LambdaInvoke(
            self,
            "divide_jobs",
            lambda_function=ssmcleaner_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )
        run_job_step = sf_tasks.LambdaInvoke(
            self,
            "run_job",
            lambda_function=ssmcleaner_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=1, interval=Duration.seconds(60)
        )
        error_check_step = sf_tasks.LambdaInvoke(
            self,
            "error_check_step",
            lambda_function=ssmcleaner_lambda,
            payload=step_functions.TaskInput.from_object({"action": "error_check"}),
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=2, interval=Duration.seconds(60)
        )

        # map steps
        divide_jobs_map = step_functions.Map(
            self,
            "divide_jobs_map",
        ).iterator(divide_jobs_step)
        run_jobs_map = step_functions.Map(
            self,
            "run_jobs_map",
        ).iterator(run_job_step)
        handle_jobs_map = step_functions.Map(
            self, "handle_jobs_map", output_path="$[0]"
        ).iterator(run_jobs_map)

        # state_machine
        state_machine_ssmcleaner = step_functions.StateMachine(
            self,
            "state_machine",
            definition=step_functions.Chain.start(init_step)
            .next(divide_jobs_map)
            .next(handle_jobs_map)
            .next(error_check_step),
        )

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
        fix_step = sf_tasks.LambdaInvoke(
            self,
            "fix",
            lambda_function=ssmcleaner_lambda,
            payload_response_only=True,
        ).add_retry(
            errors=["States.TaskFailed"], max_attempts=1, interval=Duration.seconds(60)
        )
        # map steps
        fix_map = (
            step_functions.Map(
                self,
                "fix_map",
            )
            .iterator(fix_step)
            .add_retry(
                errors=["States.TaskFailed"],
                max_attempts=1,
                interval=Duration.seconds(60),
            )
        )

        # state_machine
        state_machine_publish = step_functions.StateMachine(
            self,
            "state_machine",
            definition=step_functions.Chain.start(init_step).next(fix_map),
        )

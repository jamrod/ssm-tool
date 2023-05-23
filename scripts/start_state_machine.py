"""Start execution on an SSM Tool state machine"""
import argparse
import time
from log_it import get_logger, log_it
from layers.utilities.aws.boto3_utilities import Boto3Utilities
from layers.utilities.aws.step_function_utilities import SfnUtilities

DEV_ACCOUNT = "530786275774"
PROD_ACCOUNT = "747207162522"
ROLE_NAME = "PCMCloudAdmin"
WAIT_DELAY = 45  # time between status checks on State Machine to see if it has completed, in seconds
MAX_WAIT = (
    75  # max wait time is MAX_WAIT * WAIT_DELAY / 60, Credentials will timeout at 1 hr
)

LOGGER = get_logger("LOG_LEVEL", "info")
STATE_MACHINES = {
    "run_document-dev": "arn:aws:states:us-east-1:530786275774:stateMachine:pcm_ssm_run_document_SM",
    "deploy_document-dev": "arn:aws:states:us-east-1:530786275774:stateMachine:pcm_ssm_deploy_document_tool_SM",
    "deploy_document-prod": "arn:aws:states:us-east-1:747207162522:stateMachine:pcm_ssm_deploy_document_tool_SM",
    "get_accounts-dev": "arn:aws:states:us-east-1:530786275774:stateMachine:pcm-ami-bakery-get-accounts",
    "get_accounts-prod": "arn:aws:states:us-east-1:747207162522:stateMachine:pcm-ami-bakery-get-accounts",
}


@log_it
def start_state_machine(
    sfn_utils: SfnUtilities, arn: str, name: str, input_string: str = "{}"
) -> dict:
    """Start a state machine associated with the SSM Tool

    Parameters
        ---------
        arn : str
            state machine arn
        name : str
            name to apply to the run
        input_string : str
            Optional arguments to pass to the state machine as json string

        Returns
        -------
        dict
            {
                'executionArn': 'string',
                'startDate': datetime(2015, 1, 1)
            }
    """
    try:
        res = sfn_utils.start_execution_(
            sfn_arn=arn, name=f"SSM_Tool-{name}", sfn_input=input_string
        )
        return res["executionArn"]
    except Exception as ex:  # pylint: disable=broad-except
        msg = f"Error caught in start_state_machine\n{ex.__class__.__name__}: {str(ex)}"
        LOGGER.error(msg)
        raise Exception(msg) from ex


@log_it
def state_machine_waiter(sfn_client: SfnUtilities, exec_arn: str) -> str:
    """Monitor state machine execution and report success or failure"""
    count = 0
    while count < MAX_WAIT:
        LOGGER.info(f"Waiting {count} of {MAX_WAIT}...")
        try:
            res = sfn_client.describe_execution_(ex_arn=exec_arn)
            if res["status"] != "RUNNING":
                if res["status"] == "SUCCEEDED":
                    return "Success!"
                return "Ended with errors"
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in state_machine_waiter, Execution Arn: {exec_arn} \n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        time.sleep(WAIT_DELAY)
        count += 1
    return "Max Timeout Exceeded"


def main(stage: str, call: str, name: str, input_string: str, wait: bool) -> str:
    """Entrypoint function
    Parameters
        ---------
        stage : str
            The ci stage
        call : str
            The name of the function to call, ie 'get_accounts'
        name : str
            The name to apply to the run
        input_string : str
            Optional arguments to pass to the state machine as json string

        Returns
        -------
        str
    """
    account = DEV_ACCOUNT
    if stage == "prod":
        account = PROD_ACCOUNT
    arn = STATE_MACHINES.get(f"{call}-{stage}", None)
    if not arn:
        raise Exception(
            f"Exception in start_state_machine: Invalid name {call}-{stage}"
        )
    sfn_utils = SfnUtilities(
        Boto3Utilities().get_boto3_client(account, "stepfunctions", ROLE_NAME)
    )
    exec_arn = start_state_machine(
        sfn_utils=sfn_utils, arn=arn, name=name, input_string=input_string
    )
    LOGGER.info(f"Started {call} {stage}")
    response = f"Execution_arn: {exec_arn}"
    if wait:
        wait_resp = state_machine_waiter(sfn_client=sfn_utils, exec_arn=exec_arn)
        response += f"\n{call} {stage} {wait_resp}"
    LOGGER.info(response)
    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("env", help="The ci stage, generally 'dev' or 'prod'")
    parser.add_argument("call", help="The statemachine to start")
    parser.add_argument("name", help="name for the execution")
    parser.add_argument(
        "inputs", default="{}", nargs="?", help="Input to the state machine, optional"
    )
    parser.add_argument(
        "--wait", action="store_true", help="Wait for State Machine to finish"
    )
    args = parser.parse_args()
    print(args)
    main(
        stage=args.env,
        call=args.call,
        name=args.name,
        wait=args.wait,
        input_string=args.inputs,
    )

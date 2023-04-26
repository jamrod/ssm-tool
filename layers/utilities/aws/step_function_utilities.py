"""Module for interacting with step Functions via Boto3"""
import os
import datetime
from boto3_type_annotations.stepfunctions import Client as sfnClient  # type: ignore
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get('LOG_LEVEL', 'info'))


class SfnUtilities:
    """Methods for interacting with the boto3 aws step functions client"""
    def __init__(self, client: sfnClient) -> None:
        """Initialize a SfnUtilities object

        Parameters
        ----------
        client : sfnClient
            The boto3.client('step_function')
        """
        self.client = client

    @log_it
    def start_execution_(self, sfn_arn: str, name: str = "", sfn_input: str = "{}") -> dict:
        """Start execution of a state machine

        Parameters
        ----------
        sfn_arn : str
            The arn of the step function to start
        name : str
            The name of this invocation, a date stamp will be appended to keep the name unique
        input : str
            The input to pass to the step function as a json escaped string

        Returns
        -------
        dict
            {
                'executionArn': 'string',
                'startDate': datetime(2015, 1, 1)
            }
        """
        date_stamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        try:
            res = self.client.start_execution(
                stateMachineArn=sfn_arn,
                name=f"{name}-{date_stamp}",
                input=sfn_input
            )
            return res
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in start_execution StepFunction Arn: {sfn_arn}, Name: {name} \n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def describe_execution_(self, ex_arn: str) -> dict:
        """Get status of Step Function execution

        Parameters
        ---------
        ex_arn : str
            The arn of the step function to get status on

        Returns
        -------
        dict :
            {
                "cause": "string",
                "error": "string",
                "executionArn": "string",
                "input": "string",
                "inputDetails": {
                    "included": boolean
                },
                "mapRunArn": "string",
                "name": "string",
                "output": "string",
                "outputDetails": {
                    "included": boolean
                },
                "startDate": number,
                "stateMachineArn": "string",
                "status": "string",
                "stopDate": number,
                "traceHeader": "string"
            }
        """
        try:
            res = self.client.describe_execution(executionArn=ex_arn)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in describe_execution\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return res

    def __repr__(self):
        """return a string representation of this object"""
        return 'SfnUtilities()'


def main():
    """support for local testing"""
    print(__doc__)


if __name__ == '__main__':
    main()

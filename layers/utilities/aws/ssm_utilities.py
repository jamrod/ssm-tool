"""Module for interacting with SSM via Boto3"""
import os
from typing import List
from boto3_type_annotations.ssm import Client as ssmClient  # type: ignore
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get("LOG_LEVEL", "info"))


class SsmUtilities:
    """Methods for interacting with the boto3 aws ssm client"""

    def __init__(self, client: ssmClient) -> None:
        """Initialize a SsmUtilities object

        Parameters
        ----------
        client : ssmClient
            The boto3.client('ssm')
        """
        self.client = client

    @log_it
    def put_parameter_(self, name: str, value: str) -> bool:
        """Put a parameter value

        Parameters
        ----------
        name : str
            The name of the parameter
        value : str
            The value for the parameter
        """
        try:
            self.client.put_parameter(
                Name=name, Value=value, Type="String", Overwrite=True
            )
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in put_parameter\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return True

    @log_it
    def put_parameter_with_tags(self, name: str, value: str, tags: List[dict]) -> bool:
        """Put a parameter value

        Parameters
        ----------
        name : str
            The name of the parameter
        value : str
            The value for the parameter
        tags : List[dict]
            List of tags as dicts
        """
        try:
            self.client.put_parameter(Name=name, Value=value, Type="String", Tags=tags)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in put_parameter_with_tags\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return True

    @log_it
    def add_tags_to_parameter(self, name: str, tags: List[dict]) -> bool:
        """Add tags to a parameter

        Parameters
        ----------
        name : str
            The name of the parameter
        tags : List[dict]
            List of tags as dicts
        """
        try:
            self.client.add_tags_to_resource(
                ResourceType="Parameter", ResourceId=name, Tags=tags
            )
            LOGGER.info(f"Tags updated for {name}")
            return True
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in add_tags_to_parameter\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def send_install_command(self, instance_id: str) -> dict:
        """Send command to install amazon inspector agent"""
        try:
            res = self.client.send_command(
                InstanceIds=[instance_id],
                DocumentName="AmazonInspector-ManageAWSAgent",
                Parameters={"Operation": ["Install"]},
            )
            waiter = self.client.get_waiter("command_executed")
            waiter.wait(CommandId=res["Command"]["CommandId"], InstanceId=instance_id)
            return res
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in send_install_command\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            return {}

    @log_it
    def check_parameter(self, name: str) -> bool:
        """Confirm parameter exists by calling get_parameter
        Parameters
        ----------
        name : str
            The name of the parameter
        """
        try:
            res = self.client.get_parameter(
                Name=name,
            )
            return "Parameter" in res
        except self.client.exceptions.ParameterNotFound:
            return False
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in check_parameter\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def get_parameters_(self, names: List[str]) -> dict:
        """calls get_parameters, limit 10 per call
        Parameters
        ----------
        names : List[str]
            The name of the parameter
        """
        output = []
        limit = 10
        chunks = []
        for i in range(0, len(names), limit):
            chunks.append(names[i : i + limit])
        for chunk in chunks:
            try:
                res = self.client.get_parameters(
                    Names=chunk,
                )
                output.extend(res["Parameters"])
            except Exception as ex:  # pylint: disable=broad-except
                msg = f"Error caught in get_parameters\n{ex.__class__.__name__}: {str(ex)}"
                LOGGER.error(msg)
                raise Exception(msg) from ex
        return output

    @log_it
    def delete_parameters_(self, names=List[str]) -> dict:
        """calls delete_parameters
        Parameters
        ----------
        names : List[str]
            The name of the parameter
        """
        output = {"deleted": [], "invalid": []}
        limit = 10
        chunks = []
        for i in range(0, len(names), limit):
            chunks.append(names[i : i + limit])
        for chunk in chunks:
            try:
                res = self.client.delete_parameters(
                    Names=chunk,
                )
                if res["DeletedParameters"]:
                    output["deleted"].extend(res["DeletedParameters"])
                if res["InvalidParameters"]:
                    output["invalid"].extend(res["DeletedParameters"])
            except Exception as ex:  # pylint: disable=broad-except
                msg = f"Error caught in delete_parameters\n{ex.__class__.__name__}: {str(ex)}"
                LOGGER.error(msg)
                raise Exception(msg) from ex
        return output

    def __repr__(self):
        """return a string representation of this object"""
        return "SsmUtilities()"


def main():
    """support for local testing"""
    print(__doc__)


if __name__ == "__main__":
    main()

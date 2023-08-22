"""Module for interacting with SSM via Boto3"""
import os
from typing import List, Optional
from boto3_type_annotations.ssm import Client as ssmClient  # type: ignore

# import botocore.exceptions as Exceptions
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get("LOG_LEVEL", "info"))
S3_BUCKET = os.environ.get("S3_BUCKET", "pcm-shared-code-530786275774")
SSM_OUTPUT_PREFIX = os.environ.get("SSM_OUTPUT_PREFIX", "ssm_tool/send_command_logs/")


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
    def update_tags_on_parameter(self, name: str, tags: List[dict]) -> bool:
        """Updates tags on a parameter
        deletes tags first and replaces with new otherwise existing tag will not change value

        Parameters
        ----------
        name : str
            The name of the parameter
        tags : List[dict]
            List of tags as dicts
        """
        try:
            self.client.remove_tags_from_resource(
                ResourceType="Parameter",
                ResourceId=name,
                TagKeys=[item["Key"] for item in tags],
            )
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
            chunks.append(names[i: i + limit])
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
    def describe_parameters_(self, filters: List[dict]) -> dict:
        """Calls describe_parameters which returns info on SSM parameters filtered by the filters

        Parameters
        ----------
        filters : List[dict]
            The filter to use to reduce results
        """
        try:
            paginator = self.client.get_paginator("describe_parameters")
            res = paginator.paginate(ParameterFilters=filters)
            parameters = []
            for page in res:
                parameters.extend(page["Parameters"])
            return parameters
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in describe_parameters\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def delete_parameters_(self, names=List[str]) -> dict:
        """Delete a list of SSM parameters

        Parameters
        ----------
        names : List[str]
            The names of the parameters to delete
        """
        output = {"deleted": [], "invalid": []}
        limit = 10
        chunks = []
        for i in range(0, len(names), limit):
            chunks.append(names[i: i + limit])
        for chunk in chunks:
            try:
                res = self.client.delete_parameters(
                    Names=chunk,
                )
                if res["DeletedParameters"]:
                    output["deleted"].extend(res["DeletedParameters"])
                if res["InvalidParameters"]:
                    output["invalid"].extend(res["InvalidParameters"])
            except Exception as ex:  # pylint: disable=broad-except
                msg = f"Error caught in delete_parameters\n{ex.__class__.__name__}: {str(ex)}"
                LOGGER.error(msg)
                raise Exception(msg) from ex
        return output

    @log_it
    def list_tags_for_resource_(
        self, resource_type: str, resource_id: str
    ) -> List[dict]:
        """Returns tags for the given resource

        Parameters
        ----------
        resource_type : str
            The type of resource ie "Parameter"

        resource_id : str
            Identifier for the resource ie parameter name

        Returns
        -------
        List[dict]
            [
                {
                    "Key": "t_environment",
                    "Value": "PRD"
                },
                {
                    "Key": "t_dcl",
                    "Value": "1"
                },
                {
                    "Key": "t_AppID",
                    "Value": "SVC02522"
                }
            ]
        """
        try:
            res = self.client.list_tags_for_resource(
                ResourceType=resource_type, ResourceId=resource_id
            )
            return res["TagList"]
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in list_tags_for_resource\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def send_command_(
        self,
        document_name: str,
        instance_ids: Optional[List[str]] = None,
        targets: Optional[List[dict]] = None,
        parameters: Optional[dict] = None,
    ) -> dict:
        """calls send_command which runs a document on targeted instances

        Parameters
        ----------
        document_name : str
            The name of the document to run, uses default version

        instance_ids: Optional[List[str]]
            Instances to send command to by instance id to a max of 50, either instance_ids or targets must be used

        targets: Optional[List[dict]]
            Search criteria to determine which instances to send command to, generally tags, either instance_ids or targets must be used

        parameters: Optional[dict]
            Parameters to be passed to the document as { parameter_name: parameter_value, }

        Returns
        -------
            dict
            {
                'CommandId': 'string',
                'DocumentName': 'string',
                'DocumentVersion': 'string',
                'Comment': 'string',
                'ExpiresAfter': datetime(2015, 1, 1),
                'Parameters': {
                    'string': [
                        'string',
                    ]
                },
                'InstanceIds': [
                    'string',
                ],
                'Targets': [
                    {
                        'Key': 'string',
                        'Values': [
                            'string',
                        ]
                    },
                ],
                'RequestedDateTime': datetime(2015, 1, 1),
                'Status': 'Pending'|'InProgress'|'Success'|'Cancelled'|'Failed'|'TimedOut'|'Cancelling',
                'StatusDetails': 'string',
                'OutputS3Region': 'string',
                'OutputS3BucketName': 'string',
                'OutputS3KeyPrefix': 'string',
                'MaxConcurrency': 'string',
                'MaxErrors': 'string',
                'TargetCount': 123,
                'CompletedCount': 123,
                'ErrorCount': 123,
                'DeliveryTimedOutCount': 123,
                'ServiceRole': 'string',
                'NotificationConfig': {
                    'NotificationArn': 'string',
                    'NotificationEvents': [
                        'All'|'InProgress'|'Success'|'TimedOut'|'Cancelled'|'Failed',
                    ],
                    'NotificationType': 'Command'|'Invocation'
                },
                'CloudWatchOutputConfig': {
                    'CloudWatchLogGroupName': 'string',
                    'CloudWatchOutputEnabled': True|False
                },
                'TimeoutSeconds': 123,
                'AlarmConfiguration': {
                    'IgnorePollAlarmFailure': True|False,
                    'Alarms': [
                        {
                            'Name': 'string'
                        },
                    ]
                },
                'TriggeredAlarms': [
                    {
                        'Name': 'string',
                        'State': 'UNKNOWN'|'ALARM'
                    },
                ]
            }
        """
        output = {}
        if not instance_ids:
            instance_ids = []
        if not targets:
            targets = []
        if not parameters:
            parameters = {}
        try:
            res = self.client.send_command(
                InstanceIds=instance_ids,
                Targets=targets,
                DocumentName=document_name,
                Parameters=parameters,
                TimeoutSeconds=120,
                OutputS3Region="us-east-1",
                OutputS3BucketName=S3_BUCKET,
                OutputS3KeyPrefix=SSM_OUTPUT_PREFIX,
            )
            output = res.get("Command", output)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in send_command_\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return output

    @log_it
    def create_command_document(self, name=str, content=str, doc_format=str) -> bool:
        """Create SSM command Document

        Parameters
        ----------
        name : str
            The name for the Document, must be unique

        content : str
            Content of the document, json or yaml

        doc_format : str
            Format of the content, "JSON" or "YAML"

        """
        try:
            self.client.create_document(
                Content=content,
                Name=name,
                DocumentType="Command",
                TargetType="/AWS::EC2::Instance",
                DocumentFormat=doc_format,
            )
            return True
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in create_command_document \n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def update_document_set_default(
        self, name=str, content=str, doc_format=str
    ) -> bool:
        """Update SSM Document

        Parameters
        ----------
        name : str
            The name of the Document to update

        content : str
            Content of the document, json or yaml

        doc_format : str
            Format of the content, "JSON" or "YAML"

        """
        try:
            res = self.client.update_document(
                Content=content,
                Name=name,
                DocumentFormat=doc_format,
                DocumentVersion="$LATEST",
            )
            new_version = res["DocumentDescription"]["DocumentVersion"]
            self.client.update_document_default_version(
                Name=name, DocumentVersion=new_version
            )
            return True
        except self.client.exceptions.DuplicateDocumentContent:
            LOGGER.info(f"Document {name} has no changes, nothing to do.")
            return True
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in update_document_set_default \n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def get_document(self, name=str) -> dict:
        """Get SSM Document

        Parameters
        ----------
        name : str
            The name of the Document

        """
        res = {}
        try:
            res = self.client.describe_document(
                Name=name,
            )
        except self.client.exceptions.InvalidDocument:
            return res
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in get_document for {name} \n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return res

    @log_it
    def share_document(self, name=str, accounts=List[str]) -> bool:
        """Share an SSM Document

        Parameters
        ----------
        name : str
            The name of the Document

        accounts : List[str]
            List of accounts to share with

        """
        limit = 20
        chunked_accounts = [
            accounts[i: i + limit] for i in range(0, len(accounts), limit)
        ]
        try:
            for each_chunk_accounts in chunked_accounts:
                self.client.modify_document_permission(
                    Name=name, PermissionType="Share", AccountIdsToAdd=each_chunk_accounts
                )
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error caught in share_document for {name} \n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return True

    def __repr__(self):
        """return a string representation of this object"""
        return "SsmUtilities()"


def main():
    """support for local testing"""
    print(__doc__)


if __name__ == "__main__":
    main()

"""Tool for managing ssm documents"""
import datetime
import json
import os
from typing import Dict, List, Optional
from aws.boto3_utilities import Boto3Utilities
from aws.ssm_utilities import SsmUtilities
from aws.s3_utilities import S3Utilities
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get("LOG_LEVEL", "info"))
ROLE = os.environ.get("ROLE", "PCMCloudAdmin")
ACCOUNT = os.environ.get("S3_ACCOUNT", "530786275774")
S3_BUCKET = os.environ.get("S3_BUCKET", "pcm-shared-code-530786275774")


class SsmShareDocumentTool:
    """Tool for deploying SSM Documents"""

    def __init__(self) -> None:
        self.s3_utils = S3Utilities(
            Boto3Utilities().get_boto3_client(
                account=ACCOUNT, client_type="s3", role_name=ROLE
            )
        )

    @log_it
    def get_accounts(
        self, accounts_key: Optional[str] = "ssm_tool/accounts_list"
    ) -> dict:
        """Get the accounts to run the job in
        Accounts must be organized as json with the region as the top key with the accounts enabled for the region as a list
        {
            "us-east-1": ["530786275774", "544625599712", "584643220196"]
        }
        """
        if not accounts_key:
            accounts_key = "ssm_tool/accounts_list"
        return self.s3_utils.get_object_as_dict(bucket=S3_BUCKET, key=accounts_key)

    @log_it
    def make_jobs(self, account_list: Dict[str, list]) -> List[str]:
        """Create jobs by dividing by regions then posting to s3

        Parameters
        ---------
        account_list : Dict[str, list]
            list of accounts organized by enabled region, or just a dict of regions
            {
                "us-east-1": ["530786275774", "584643220196"]
            }

        Returns
        -------
        List[str]
            [
                "ssm_tool/deploy_document/jobs/us-east-1"
            ]
        """
        job_keys = []
        for region in account_list:
            key_name = f"ssm_tool/deploy_document/jobs/{region}"
            self.s3_utils.put_object_(
                data=json.dumps(account_list[region]),
                bucket=S3_BUCKET,
                key=key_name,
            )
            job_keys.append(key_name)
        return job_keys

    @log_it
    def get_documents(self) -> List[dict]:
        """Return documents stored on S3"""
        try:
            documents = []
            doc_keys = self.s3_utils.list_bucket_keys(
                bucket=S3_BUCKET, prefix="ssm_tool/ssm_documents/"
            )
            for key_dict in doc_keys:
                key = key_dict["Key"]
                doc_content = self.s3_utils.get_object_as_dict(
                    bucket=S3_BUCKET, key=key
                )
                doc_name = key[key.rfind("/") + 1: key.rfind(".")]
                doc_ext = key[key.rfind(".")+1:].upper()
                if doc_ext == "JSON":
                    doc_format = doc_ext
                elif doc_ext in ("YML", "YAML"):
                    doc_format = "YAML"
                else:
                    raise SsmToolException(
                        f"Invalid document type: {doc_ext}, must be JSON or YAML"
                    )
                documents.append(
                    {"name": doc_name, "content": json.dumps(doc_content), "doc_format": doc_format}
                )
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in get_documents \ntype: {ex.__class__.__name__} : {ex}"
            self.post_error(err=msg, caller="get_documents")
        return documents

    @log_it
    def deploy_documents(
        self, region: str, accounts: Optional[List[str]] = None
    ) -> bool:
        """Create/update documents and/or optionally share to a list of accounts

        Parameters
        ----------
        region : str
            Region, us-east-1
        accounts : List[str]
            Accounts to share document with
        """
        documents = self.get_documents()
        try:
            ssm_utils = SsmUtilities(
                Boto3Utilities().get_boto3_client(
                    account=ACCOUNT, client_type="ssm", role_name=ROLE, region=region
                )
            )
            for document in documents:
                res = ssm_utils.get_document(document["name"])
                if res:
                    ssm_utils.update_document_set_default(
                        name=document["name"],
                        content=document["content"],
                        doc_format=document["doc_format"],
                    )
                else:
                    ssm_utils.create_command_document(
                        name=document["name"],
                        content=document["content"],
                        doc_format=document["doc_format"],
                    )
                if accounts:
                    ssm_utils.share_document(
                        name=document["name"],
                        accounts=accounts,
                    )
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in deploy_document for {region}\ntype: {ex.__class__.__name__} : {ex}"
            self.post_error(err=msg, caller=f"deploy_documents/{region}")
        return True

    @log_it
    def post_error(self, err: str, caller: str) -> bool:
        """Post error to S3"""
        timestamp = datetime.datetime.utcnow()
        key_name = f"ssm_tool/deploy_document/errors/{caller}/{timestamp.strftime('%Y%m%d-%H%M%S%f')}.txt"
        self.s3_utils.put_object_(
            data=json.dumps(err, default=str, indent=2),
            bucket=S3_BUCKET,
            key=key_name,
        )
        return True

    @log_it
    def clean_up_s3(self, to_clean: list) -> bool:
        """Remove files from previous run"""
        try:
            for prefix in to_clean:
                keys = self.s3_utils.list_bucket_keys(bucket=S3_BUCKET, prefix=prefix)
                self.s3_utils.delete_objects_(bucket=S3_BUCKET, keys=keys)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception caught in clean_up_s3 \ntype: {ex.__class__.__name__} : {ex}"
            LOGGER.error(msg)
            self.post_error(err=msg, caller="clean_up_s3")
        return True

    @log_it
    def check_for_errors(self) -> bool:
        """Check s3 bucket for files with ssm_tool/deploy_document/errors/ prefix"""
        errors = []
        try:
            keys = self.s3_utils.list_bucket_keys(
                bucket=S3_BUCKET, prefix="ssm_tool/deploy_document/errors/"
            )
            if keys:
                for key in keys:
                    errors.append(key["Key"])
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception caught in check_for_errors \n{ex}"
            LOGGER.error(msg)
            self.post_error(err=msg, caller="check_for_errors")
            raise SsmToolException(msg) from ex
        if errors:
            msg = f"Errors detected in ssm_deploy_document_tool, check {S3_BUCKET}/ssm_tool/deploy_document/errors/ \nError file(s): {str(errors)}"
            LOGGER.error(msg)
            raise SsmToolException(msg)
        return True


class SsmToolException(Exception):
    """Exception for any failure in the SsmTool lambda"""


@log_it
def main(app, event: Dict[str, str]):
    """handle action"""
    res = {}
    action = event.get("action")
    try:
        if action == "init":
            app.clean_up_s3(
                to_clean=[
                    "ssm_tool/deploy_document/jobs/",
                    "ssm_tool/deploy_document/errors/",
                ]
            )
            if "accounts_key" in event:
                account_list = app.get_accounts(
                    accounts_key=event.get("accounts_key", None)
                )
            else:
                regions = Boto3Utilities().get_region_list(ACCOUNT)
                account_list = {region: [] for region in regions}
            job_keys = app.make_jobs(
                account_list=account_list,
            )
            res = [{"action": "deploy", "s3_key": key} for key in job_keys]
        elif action == "deploy":
            s3_key = event.get("s3_key")
            region = s3_key[s3_key.rfind('/')+1:]
            accounts = app.s3_utils.get_object_as_dict(
                bucket=S3_BUCKET, key=s3_key
            )
            app.deploy_documents(region=region, accounts=accounts)
            res = {"action": "error_check"}
        elif action == "error_check":
            app.check_for_errors()
            res = {"result": "Success!"}
        else:
            timestamp = datetime.datetime.utcnow()
            msg = f"Unknown action, {action}, in event at {timestamp}"
            LOGGER.error(msg)
            raise SsmToolException(msg)
    except Exception as ex:  # pylint: disable=broad-except
        msg = f"Exception caught in ssm_deploy_document_tool at {action} \ntype: {ex.__class__.__name__} : {ex}"
        LOGGER.error(msg)
        raise Exception(msg) from ex
    return res


def lambda_handler(event, context):
    """support for AWS Lambda execution"""
    LOGGER.info(
        f"starting ssm_deploy_document_tool.lambda_handler with event: {event} and context: {context}"
    )
    app_instance = SsmShareDocumentTool()
    return main(app=app_instance, event=event)


if __name__ == "__main__":
    # for local testing
    test_event = {'action': 'error_check'}
    app_instance_ = SsmShareDocumentTool()
    print(main(app=app_instance_, event=test_event))

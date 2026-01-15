"""Tool for changing ssm_parameters"""
import datetime
import json
import os
from typing import Dict, List
from aws.boto3_utilities import Boto3Utilities
from aws.ssm_utilities import SsmUtilities
from aws.s3_utilities import S3Utilities
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get("LOG_LEVEL", "info"))
ROLE = os.environ.get("ROLE", "PCMCloudAdmin")
S3_ACCOUNT = os.environ.get("S3_ACCOUNT", "account1")
S3_BUCKET = os.environ.get("S3_BUCKET", "mybucket-account1")
STAGE = os.environ.get("STAGE", "dev")


class SsmRunDocumentTool:
    """Tool for running SSM Documents on instances"""

    def __init__(self) -> None:
        self.s3_utils = S3Utilities(
            Boto3Utilities().get_boto3_client(
                account=S3_ACCOUNT, client_type="s3", role_name=ROLE
            )
        )

    @log_it
    def make_jobs(self, args: dict, instance_list: List[dict]) -> List[str]:
        """Create jobs by chunking accounts into batches and dividing by regions
        then posting to s3

        Parameters
        ---------
        args : dict
            Dict of args to be passed to the job
            {
                "document": "CrowdStrikeFalconInstall-ubuntu",
                "instance_ids": ["i-01c20c9d586abe17a"],
                "parameters": {...}
            }

        instance_list : dict
            list of ec2 instances organized by region and account
            {
                "us-east-1": {
                    "account1": ["i-01c20c9d586abe17a"],
                    "584643220196": ["i-05b2555a3380b2279"]
            }

        Returns
        -------
        List[str]
            [
                "ssm_tool/run_document/jobs/us-east-1-0"
            ]
        """
        job_keys = []
        for region in instance_list:
            accounts = instance_list[region]
            jobs = []
            for account, instance_ids in accounts.items():
                batches = self.chunk_instances(instances=instance_ids)
                for batch in batches:
                    args["instance_ids"] = batch
                    jobs.append({"region": region, "account": account, "args": args})
            self.chunk_jobs(
                jobs=jobs,
                region=region,
                s3_prefix="ssm_tool/run_document/jobs",
                max_batches=100,
            )
            job_keys.append(f"ssm_tool/run_document/jobs/{region}/")
        return job_keys

    @log_it
    def chunk_jobs(
        self, jobs: List[dict], region: str, s3_prefix: str, max_batches: int
    ) -> bool:
        """Chunk jobs into max_batches batches or less per region

        Parameters
        ---------
        jobs : List[dict]
            List of jobs as dicts with the region and the account

        region : str
            Region jobs will run in

        s3_prefix : str
            s3 prefix to save batches to

        """
        number_of_batches = len(jobs) if len(jobs) < max_batches else max_batches
        job_groups = {
            f"batch-{x}": [] for x in range(0, number_of_batches)
        }  # make batches to the max, then spread jobs evenly accross batches
        while jobs:
            for batch in job_groups:
                if not jobs:
                    break
                job_groups[batch].append(jobs.pop(0))
        for batch in job_groups:
            key_name = f"{s3_prefix}/{region}/{batch}"
            self.s3_utils.put_object_(
                data=json.dumps(job_groups[batch]),
                bucket=S3_BUCKET,
                key=key_name,
            )
        return True

    @log_it
    def chunk_instances(self, instances: List[str]) -> List[list]:
        """Chunk instance_ids into batches of 50 or less"""
        batches = []
        for i in range(0, len(instances), 50):
            batches.append(instances[i: i + 50])
        return batches

    @log_it
    def get_jobs(self, s3_path: str) -> list:
        """Get batch of jobs from s3"""
        return self.s3_utils.get_object_as_dict(bucket=S3_BUCKET, key=s3_path)

    @log_it
    def run_job(self, job: dict) -> bool:
        """Execute job

        Parameters
        ----------
        job : dict
            Dict containing the job and args
        """
        region = job.get("region", "us-east-1")
        account = job.get("account")
        args = job.get("args")
        document = args.get("document")
        instance_ids = args.get("instance_ids")
        targets = args.get("targets")
        parameters = args.get("parameters")
        self.clean_up_s3(
            to_clean=[f"ssm_tool/run_document/errors/run_job/{region}/{account}/"]
        )
        try:
            ssm_utils = SsmUtilities(
                Boto3Utilities().get_boto3_client(
                    account=account, client_type="ssm", role_name=ROLE, region=region
                )
            )
            ssm_utils.send_command_(
                document_name=document,
                instance_ids=instance_ids,
                targets=targets,
                parameters=parameters,
            )
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in run_job for {region}-{account}\ntype: {ex.__class__.__name__} : {ex}"
            self.post_error(err=msg, caller=f"run_job/{region}/{account}")
        return True

    @log_it
    def post_error(self, err: str, caller: str) -> bool:
        """Post error to S3"""
        timestamp = datetime.datetime.utcnow()
        key_name = f"ssm_tool/run_document/errors/{caller}/{timestamp.strftime('%Y%m%d-%H%M%S%f')}.txt"
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
        """Check s3 bucket for files with ssm_tool/run_document/errors/ prefix"""
        errors = []
        try:
            keys = self.s3_utils.list_bucket_keys(
                bucket=S3_BUCKET, prefix="ssm_tool/run_document/errors/"
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
            msg = f"Errors detected in ssm_run_document_tool, check {S3_BUCKET}/ssm_tool/run_document/errors/ \nError file(s): {str(errors)}"
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
                    "ssm_tool/run_document/jobs/",
                    "ssm_tool/run_document/errors/",
                ]
            )
            instance_list = app.s3_utils.get_object_as_dict(
                bucket=S3_BUCKET,
                key=event.get("instance_list", "ssm_tool/run_document/instance_list"),
            )
            job_keys = app.make_jobs(
                args=event.get("args"),
                instance_list=instance_list,
            )
            res = [{"action": "divide_jobs", "s3_key": key} for key in job_keys]
        elif action == "divide_jobs":
            jobs = app.s3_utils.list_bucket_keys(
                bucket=S3_BUCKET, prefix=event.get("s3_key")
            )
            res = [{"action": "run_job", "job_key": job["Key"]} for job in jobs]
        elif action == "run_job":
            jobs = app.get_jobs(event.get("job_key"))
            for job in jobs:
                app.run_job(job)
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
        msg = f"Exception caught in ssm_parameter_tool at {action} \ntype: {ex.__class__.__name__} : {ex}"
        LOGGER.error(msg)
        raise Exception(msg) from ex
    return res


def lambda_handler(event, context):
    """support for AWS Lambda execution"""
    LOGGER.info(
        f"starting ssm_run_document_tool.lambda_handler with event: {event} and context: {context}"
    )
    app_instance = SsmRunDocumentTool()
    return main(app=app_instance, event=event)


if __name__ == "__main__":
    # for local testing
    test_event = {
        "action": "init",
        "args": {
            "document": "CrowdStrikeFalconInstall-ubuntu",
            "parameters": {"presignedurl": "https://#", "activate": "False"},
        },
    }
    app_instance_ = SsmRunDocumentTool()
    print(main(app=app_instance_, event=test_event))

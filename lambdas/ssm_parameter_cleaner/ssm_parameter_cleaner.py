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
S3_ACCOUNT = os.environ.get("S3_ACCOUNT", "119377359737")
S3_BUCKET = os.environ.get("S3_BUCKET", "ami-bakery-data-119377359737-us-east-1")
STAGE = os.environ.get("STAGE", "DEV")
TAGS = [
    {"Key": "t_environment", "Value": STAGE},
    {"Key": "t_AppID", "Value": "SVC02522"},
    {"Key": "t_dcl", "Value": "1"},
]
DISTROS = [
    "amzneks1.19",
    "amzneks1.20",
    "amzneks1.21",
    "amzneks1.22",
    "amzneks1.23",
    "amznlinux2",
    "amznlinux2022arm",
    "amznlinux2022min_arm",
    "amznlinux2022min_x86_64",
    "amznlinux2022x86_64",
    "amznlinux2arm",
    "amznlinux2armecs",
    "amznlinux2armkernel5.10",
    "amznlinux2ecs",
    "amznlinux2gpuoptimized",
    "amznlinux2kernel5.10",
    "centos7",
    "oraclelinux8",
    "rhel8",
    "ubuntu18",
    "ubuntu20",
    "windows2016",
    "windows2019",
    "windows2019byol",
    "windows2019byol-gui",
    "windows2019byol-standard",
    "windows2022",
]


class SSMCleaner:
    """Fix ssm duplicate parameter in PCM managed accounts"""

    def __init__(self) -> None:
        self.s3_utils = S3Utilities(
            Boto3Utilities().get_boto3_client(S3_ACCOUNT, "s3", ROLE)
        )

    @log_it
    def make_jobs(self, action: str) -> List[str]:
        """Create jobs

        Returns
        -------
        List[str]
            [
                "ssm_tool/jobs/us-east-1"
            ]
        """
        account_list = self.s3_utils.get_object_as_dict(
            bucket=S3_BUCKET, key="account_list"
        )
        job_keys = []
        for region in account_list:
            accounts = account_list[region]
            jobs = [
                {"action": action, "region": region, "account": account}
                for account in accounts
            ]
            self.chunk_jobs(jobs=jobs, region=region)
            job_keys.append(f"ssm_tool/jobs/{region}/")
        return job_keys

    @log_it
    def chunk_jobs(self, jobs: List[dict], region: str) -> bool:
        """Chunk jobs into 100 batches for the run step

        Parameters
        ---------
        jobs : List[dict]
            List of jobs as dicts with the region and the account

        region : str
            Region jobs will run in

        """
        LOGGER.info(f"How many jobs : {len(jobs)}")
        number_of_batches = len(jobs) if len(jobs) < 100 else 100
        job_groups = {
            f"batch-{x}": [] for x in range(0, number_of_batches)
        }  # make batches to a max of 100, then spread jobs evenly accross batches
        while jobs:
            for batch in job_groups:
                if not jobs:
                    break
                job_groups[batch].append(jobs.pop(0))
        for batch in job_groups:
            key_name = f"ssm_tool/jobs/{region}/{batch}"
            self.s3_utils.put_object_(
                data=json.dumps(job_groups[batch]),
                bucket=S3_BUCKET,
                key=key_name,
            )
        return True

    @staticmethod
    @log_it
    def fix_duplicates(region: str, account: str) -> dict:
        """Correct for duplicate ssm parameter creation. Moves the value from the duplicate to the original then deletes the duplicate
        Parameters
        ----------
        region : str
            The region to operate in
        account : str
            The account to operate in

        Returns
            Dict[str, str]
                {
                    "not_updated": [],
                    "not_deleted": []
                }
        """
        results = {"not_updated": [], "not_deleted": []}
        param_names_upper = []
        try:
            for dist_name in DISTROS:
                param_names_upper.append(f"pcm-{dist_name}-{STAGE}-latest")
            delete_list = []
            ssm_util = SsmUtilities(
                Boto3Utilities().get_boto3_client(
                    account=account, client_type="ssm", role_name=ROLE, region=region
                )
            )
            param_res = ssm_util.get_parameters_(names=param_names_upper)
            for param in param_res:
                lower_param = param["Name"].lower()
                if ssm_util.check_parameter(name=lower_param):
                    updated = ssm_util.put_parameter_(
                        name=lower_param, value=param["Value"]
                    )
                else:
                    updated = ssm_util.put_parameter_with_tags(
                        name=lower_param, value=param["Value"], tags=TAGS
                    )
                if updated:
                    delete_list.append(param["Name"])
                else:
                    results["not_updated"].append(f"{region}-{account}-{param['Name']}")
            if delete_list:
                del_res = ssm_util.delete_parameters_(names=delete_list)
                if del_res["invalid"]:
                    for invalid_param in del_res["invalid"]:
                        results["not_deleted"].append(
                            f"{region}-{account}-{invalid_param}"
                        )
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in fix_duplicates for {region}-{account}\ntype: {ex.__class__.__name__} : {ex}"
            raise Exception(msg) from ex
        return results

    @log_it
    def fix_tags(self, account: str, region: str, to_update: str) -> True:
        """Update tags to 'PRD' or 'DEV' if 'prod' or 'dev'"""
        try:
            ssm_util = SsmUtilities(
                Boto3Utilities().get_boto3_client(
                    account=account, client_type="ssm", role_name=ROLE, region=region
                )
            )
            count = 0
            #  get all parameters with wrong tags
            params_needing_update = ssm_util.describe_parameters_(
                filters=[{"Key": "tag:t_environment", "Values": [to_update]}]
            )
            param_names = [param["Name"] for param in params_needing_update]
            params = ssm_util.get_parameters_(names=param_names)
            for param in params:
                updated = ssm_util.update_tags_on_parameter(
                    name=param["Name"], tags=TAGS
                )
                if updated:
                    count += 1
            LOGGER.info(
                f"{len(params)} needed updating, {count} got updated in {account} {region}"
            )
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in fix_tags for {region}-{account}\ntype: {ex.__class__.__name__} : {ex}"
            self.post_error(err=msg, caller="fix_tags")
        return True

    @log_it
    def post_error(self, err: str, caller: str) -> bool:
        """Post error to S3"""
        timestamp = datetime.datetime.utcnow()
        key_name = (
            f"ssm_tool/errors/{caller}_{timestamp.strftime('%Y%m%d-%H%M%S%f')}.txt"
        )
        self.s3_utils.put_object_(
            data=json.dumps(err, default=str, indent=2),
            bucket=S3_BUCKET,
            key=key_name,
        )
        return True

    @log_it
    def get_jobs(self, s3_path: str) -> list:
        """Get batch of jobs from s3"""
        return self.s3_utils.get_object_as_dict(bucket=S3_BUCKET, key=s3_path)

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
        """Check s3 bucket for files with ssm_tool/errors/ prefix"""
        errors = []
        try:
            keys = self.s3_utils.list_bucket_keys(
                bucket=S3_BUCKET, prefix="ssm_tool/errors/"
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
            msg = f"Errors detected in ssm_tool, check {S3_BUCKET}/ssm_tool/errors/ \nError file(s): {str(errors)}"
            LOGGER.error(msg)
            raise SsmToolException(msg)
        return True


class SsmToolException(Exception):
    """Exception for any failure in the SsmTool lambda"""


@log_it
def main(app, event: Dict[str, str]):
    """handle action"""
    res = {}
    try:
        if event["action"] == "init":
            app.clean_up_s3(to_clean=["ssm_tool"])
            job_keys = app.make_jobs(action="fix")
            res = [{"action": "divide_jobs", "s3_key": key} for key in job_keys]
        if event["action"] == "divide_jobs":
            jobs = app.s3_utils.list_bucket_keys(
                bucket=S3_BUCKET, prefix=event.get("s3_key")
            )
            res = [{"action": "run_job", "job_key": job["Key"]} for job in jobs]
        if event["action"] == "run_job":
            bad_tag = "dev"
            if STAGE == "PRD":
                bad_tag = "prod"
            jobs = app.get_jobs(event.get("job_key"))
            for job in jobs:
                app.fix_tags(
                    region=job.get("region"), account=job.get("account"), to_update=bad_tag
                )
                res = {"action": "error_check"}
                LOGGER.info(
                    f"Fix {bad_tag} for {job.get('account')} {job.get('region')}"
                )
        if event["action"] == "error_check":
            app.check_for_errors()
            res = {"result": "Success!"}
    except Exception as ex:  # pylint: disable=broad-except
        info = f"{event.get('action')}"
        msg = (
            f"Exception caught in fix_ssm {info} \ntype: {ex.__class__.__name__} : {ex}"
        )
        LOGGER.error(msg)
        app.post_error(err=msg)
        raise Exception(msg) from ex
    return res


def lambda_handler(event, context):
    """support for AWS Lambda execution"""
    LOGGER.info(
        f"starting fix_ssm.lambda_handler with event: {event} and context: {context}"
    )
    app_instance = SSMCleaner()
    return main(app=app_instance, event=event)


if __name__ == "__main__":
    # for local testing
    test_event = {"action": "error_check"}
    app_instance_ = SSMCleaner()

    print(main(app=app_instance_, event=test_event))

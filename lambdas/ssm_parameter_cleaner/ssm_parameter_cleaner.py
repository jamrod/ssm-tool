"""Fixes mistaken ssm parameter duplication"""
import datetime
import json
import os
from typing import Dict, List
from aws.boto3_utilities import Boto3Utilities
from aws.ssm_utilities import SsmUtilities
from aws.s3_utilities import S3Utilities
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get("LOG_LEVEL", "info"))
PIPELINE_ACCOUNT = os.environ.get("PIPELINE_ACCOUNT", "056952386373")  # techops-dev
ROLE = os.environ.get("ROLE", "PCMCloudAdmin")
S3_ACCOUNT = os.environ.get("S3_ACCOUNT", "056952386373")
S3_BUCKET = os.environ.get("S3_BUCKET", "ami-bakery-data-056952386373-us-east-1")
STAGE = os.environ.get("STAGE", "DEV")
TAGS = [
    {"Key": "t_environment", "Value": "dev"},
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
    def init_fix(self, region: str) -> List[dict]:
        """Start ssm fix for specified region
        Parameters
        ----------
        region : str

        Returns
        -------
        List[dict]
            [
                {"action": "fix", "region": "us-east-1", "account": "111111111"}
            ]
        """
        account_list = self.s3_utils.get_object_as_dict(
            bucket=S3_BUCKET, key="account_list"
        )
        accounts = account_list[region]
        return [
            {"action": "fix", "region": region, "account": account}
            for account in accounts
        ]

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
                        name=lower_param, value=f"{param['Value']}"
                    )
                else:
                    updated = ssm_util.put_parameter_with_tags(
                        name=lower_param, value=f"{param['Value']}", tags=TAGS
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
    def post_error(self, err: str) -> bool:
        """Post error to S3"""
        timestamp = datetime.datetime.utcnow()
        key_name = f"errors/fix_ssm/{timestamp.strftime('%Y%m%d-%H%M%S%f')}.txt"
        self.s3_utils.put_object_(
            data=json.dumps(err),
            bucket=S3_BUCKET,
            key=key_name,
        )
        return True

    @log_it
    def chunk_jobs(self, jobs: List[dict], region: str) -> List[dict]:
        """Chunk jobs into 100 batches for the fix step

        Parameters
        ---------
        jobs : List[dict]
            List of jobs as dicts with the region and the account

        Returns
        -------
        List[dict]
            List of job batches which have the key for the batch of jobs on s3

        [
            {
                "action": "fix",
                "s3_key": "publish/amzneks1.23/set-ssm-jobs/batch-us-west-2-0"
            }
        ]
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
        batches = []
        for batch in job_groups:
            key_name = f"fix_ssm/{region}/fix-jobs/{batch}"
            self.s3_utils.put_object_(
                data=json.dumps(job_groups[batch]),
                bucket=S3_BUCKET,
                key=key_name,
            )
            batches.append(
                {
                    "action": "fix",
                    "s3_key": key_name,
                }
            )
        return batches

    @log_it
    def get_jobs(self, s3_path: str) -> list:
        """Get batch of jobs from s3"""
        return self.s3_utils.get_object_as_dict(bucket=S3_BUCKET, key=s3_path)


@log_it
def main(app, event: Dict[str, str]):
    """handle action"""
    res = {}
    try:
        if event["action"] == "init":
            account_jobs = app.init_fix(region=event.get("region"))
            res = app.chunk_jobs(jobs=account_jobs, region=event.get("region"))
        if event["action"] == "fix":
            jobs = app.get_jobs(event.get("s3_key"))
            for job in jobs:
                res = app.fix_duplicates(
                    region=job.get("region"), account=job.get("account")
                )
                LOGGER.info(
                    msg=f"Results for {job.get('region')} {job.get('account')}: {res}"
                )
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
    test_event = {"action": "init", "region": "ap-northeast-3"}
    app_instance_ = SSMCleaner()
    output = main(app=app_instance_, event=test_event)
    # print(output)
    with open(
        "python/scratch/lambda_ssm_fix_output.json", "w", encoding="utf-8"
    ) as write_file:
        json.dump(output, write_file, indent=2)

"""Tool for changing ssm_parameters"""
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
S3_ACCOUNT = os.environ.get("S3_ACCOUNT", "account2")
S3_BUCKET = os.environ.get("S3_BUCKET", "mybucket-account2")
STAGE = os.environ.get("STAGE", "DEV")
TAGS = [
    {"Key": "t_environment", "Value": os.environ.get("T_ENV_TAG", "DEV")},
    {"Key": "t_AppID", "Value": ""},
    {"Key": "t_dcl", "Value": "1"},
]


class SsmParameterTool:
    """Tool for interacting with the ssm parameter store on PCM managed accounts"""

    def __init__(self) -> None:
        self.s3_utils = S3Utilities(
            Boto3Utilities().get_boto3_client(
                account=S3_ACCOUNT, client_type="s3", role_name=ROLE
            )
        )

    @log_it
    def get_accounts(
        self, accounts_key: Optional[str] = "ssm_tool/accounts_list"
    ) -> dict:
        """Get the accounts to run the job in
        Accounts must be organized as json with the region as the top key with the accounts enabled for the region as a list
        {
            "us-east-1": ["account2", "544625599712", "584643220196"]
        }
        """
        if not accounts_key:
            accounts_key = "ssm_tool/accounts_list"
        return self.s3_utils.get_object_as_dict(bucket=S3_BUCKET, key=accounts_key)

    @log_it
    def make_jobs(self, action: str, args: dict, account_list: Dict[str, list]) -> List[str]:
        """Create jobs by chunking accounts into batches and dividing by regions
        then posting to s3

        Parameters
        ---------
        action : str
            action for each job

        args : dict
            Dict of args to be passed to the job
            {
                "to_update": "DEV"
            }

        account_list : dict
            list of accounts organized by enabled region
            {
                "us-east-1": ["account2", "584643220196"]
            }

        Returns
        -------
        List[str]
            [
                "ssm_tool/jobs/us-east-1-0"
            ]
        """
        job_keys = []
        for region in account_list:
            accounts = account_list[region]
            jobs = [
                {"action": action, "region": region, "account": account, "args": args}
                for account in accounts
            ]
            self.chunk_jobs(
                jobs=jobs, region=region, s3_prefix="ssm_tool/jobs", max_batches=100
            )
            job_keys.append(f"ssm_tool/jobs/{region}/")
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
    def create_update_parameters(
        self, ssm_util: SsmUtilities, names_values: Dict[str, str], tags: List[dict]
    ) -> bool:
        """Add or update one or more new ssm parameters

        Parameters
        ----------
        ssm_util : SsmUtilities
            An instance of SsmUtilities

        names_values : Dict[str:str]
            keys are the Name of the parameter and the values are the Value of the parameter
            {"special_ami": "ami-0123456789"}

        """
        try:
            for param in names_values:
                value = names_values[param]
                if ssm_util.check_parameter(
                    name=param
                ):  # if parameter name already exists, tags must be added in a separate call
                    ssm_util.put_parameter_(name=param, value=value)
                    ssm_util.add_tags_to_parameter(name=param, tags=tags)
                else:
                    ssm_util.put_parameter_with_tags(name=param, value=value, tags=tags)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in create_update_parameter for \ntype: {ex.__class__.__name__} : {ex}"
            raise SsmToolException(msg) from ex
        return True

    @log_it
    def rename_parameters(self, ssm_util: SsmUtilities, names: Dict[str, str]) -> bool:
        """Moves the value from a list of parameters to a new name then deletes the original parameter

        Parameters
        ----------
        ssm_util : SsmUtilities
            An instance of SsmUtilities

        names : Dict[str:str]
            keys are the names to change values are what they are changed to {"old_name": "new_name"}

        """
        delete_list = []
        try:
            params = ssm_util.get_parameters_(names=list(names.keys()))
            for param in params:
                new_name = names[param["Name"]]
                if ssm_util.check_parameter(name=new_name):
                    updated = ssm_util.put_parameter_(
                        name=new_name, value=param["Value"]
                    )
                else:
                    tags = ssm_util.list_tags_for_resource_(
                        resource_type="Parameter", resource_id=param["Name"]
                    )
                    updated = ssm_util.put_parameter_with_tags(
                        name=new_name, value=param["Value"], tags=tags
                    )
                if updated:
                    delete_list.append(param["Name"])
                else:
                    msg = f"Did not update: {param['Name']}"
                    raise Exception(msg)
            if delete_list:
                del_res = ssm_util.delete_parameters_(names=delete_list)
                if del_res["invalid"]:
                    msg = f"These parameters did not delete for reason 'invalid': {str(del_res['invalid'])}"
                    LOGGER.error(msg)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in rename_parameters \ntype: {ex.__class__.__name__} : {ex}"
            raise SsmToolException(msg) from ex
        return True

    @log_it
    def fix_tags(
        self,
        ssm_util: SsmUtilities,
        to_update: Dict[str, list],
        new_tags: Dict[str, str],
    ) -> bool:
        """Update tags if parameter has a tag value matching to_update

        Parameters
        ----------
        ssm_util : SsmUtilities
            An instance of SsmUtilities

        to_update : Dict[str,list]
            The tag values to search for as key value pairs, the tag name is the key, possible values are a list
            If one tag value matches, all tags will be replaced for that parameter
            {
                "t_environment": ["prd", "prod"]
            }

        new_tags : List[dict]
            List of dicts of tag key value pairs, see TAGS global

        Returns
        -------
            Bool
        """
        try:
            for tag_key in to_update:
                #  get all parameters with wrong tags
                params_needing_update = ssm_util.describe_parameters_(
                    filters=[{"Key": f"tag:{tag_key}", "Values": to_update[tag_key]}]
                )
                param_names = [param["Name"] for param in params_needing_update]
                for param in param_names:
                    ssm_util.update_tags_on_parameter(name=param, tags=new_tags)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in fix_tags \ntype: {ex.__class__.__name__} : {ex}"
            raise SsmToolException(msg) from ex
        return True

    @log_it
    def remove_parameters(self, ssm_util: SsmUtilities, names: List[str]) -> bool:
        """Delete named parameter(s)

        Parameters
        ----------
        ssm_util : SsmUtilities
            An instance of SsmUtilities

        names: List[str]
            List of parameters to delete by name

        Returns
        -------
            Bool
        """
        try:
            del_res = ssm_util.delete_parameters_(names=names)
            if del_res["invalid"]:
                msg = f"These parameters did not delete for reason 'invalid': {str(del_res['invalid'])}"
                LOGGER.info(msg)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in delete_parameters \ntype: {ex.__class__.__name__} : {ex}"
            raise SsmToolException(msg) from ex
        return True

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
        action = job.get("action")
        args = job.get("args")
        tags = args.get("tags")
        if not tags:
            tags = TAGS
        self.clean_up_s3(
            to_clean=[f"ssm_tool/errors/run_job/{action}/{region}/{account}/"]
        )
        try:
            ssm_util = SsmUtilities(
                Boto3Utilities().get_boto3_client(
                    account=account, client_type="ssm", role_name=ROLE, region=region
                )
            )
            if action in ("create", "update"):
                self.create_update_parameters(
                    ssm_util=ssm_util,
                    names_values=args.get("names_values"),
                    tags=tags,
                )
            elif action == "rename":
                self.rename_parameters(ssm_util=ssm_util, names=args.get("names"))
            elif action == "fix_tags":
                self.fix_tags(
                    ssm_util=ssm_util,
                    to_update=args.get("to_update"),
                    new_tags=tags,
                )
            elif action == "remove":
                self.remove_parameters(ssm_util=ssm_util, names=args.get("names"))
            else:
                msg = f"Unknown action: {action} in run_job from job: {job}"
                LOGGER.error(msg)
                raise SsmToolException(msg)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Error in run_job for {region}-{account}\ntype: {ex.__class__.__name__} : {ex}"
            self.post_error(err=msg, caller=f"run_job/{action}/{region}/{account}")
        return True

    @log_it
    def post_error(self, err: str, caller: str) -> bool:
        """Post error to S3"""
        timestamp = datetime.datetime.utcnow()
        key_name = (
            f"ssm_tool/errors/{caller}/{timestamp.strftime('%Y%m%d-%H%M%S%f')}.txt"
        )
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
    action = event.get("action")
    try:
        if action == "init":
            app.clean_up_s3(to_clean=["ssm_tool/jobs/", "ssm_tool/errors/"])
            account_list = app.get_accounts(accounts_key=event.get("accounts_key"))
            job_keys = app.make_jobs(
                action=event.get("job_action"),
                args=event.get("args"),
                account_list=account_list,
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
        f"starting ssm_parameter_tool.lambda_handler with event: {event} and context: {context}"
    )
    app_instance = SsmParameterTool()
    return main(app=app_instance, event=event)


if __name__ == "__main__":
    # for local testing
    test_event = {"action": "run_job", "job_key": "ssm_tool/jobs/us-west-2/batch-2"}
    app_instance_ = SsmParameterTool()
    # ssm_util_ = SsmUtilities(
    #     Boto3Utilities().get_boto3_client(
    #         account="account1",
    #         client_type="ssm",
    #         role_name=ROLE,
    #         region="us-east-1",
    #     )
    # )
    print(main(app=app_instance_, event=test_event))
    # res_ = app_instance_.get_accounts()
    # with open("scratch/accounts.json", "w", encoding="utf-8") as writef:
    #     json.dump(res_, writef, indent=2, default=str)

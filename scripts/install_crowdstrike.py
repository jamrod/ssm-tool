"""Install CrowdStrike on a set of instances"""
import argparse
import json
import start_state_machine
from aws.boto3_utilities import Boto3Utilities
from layers.utilities.aws.s3_utilities import S3Utilities

STAGE = "dev"
S3_BUCKET = "mybucket-account"
ROLE = "PCMCloudAdmin"
ACCOUNT = "account"
INSTALLS_BUCKET = "prsn-downloadable-restricted-artifacts-us-east-1-account"


def trigger_crowdstrike_install(install: str, document: str, instances_fp: str) -> bool:
    """Build event and trigger state machine to run crowdstirke install

    Paramters
        ---------
        install : str
            The name of the install file as it is in INSTALLS_BUCKET
        document : str
            The name of the document, ie "CrowdStrikeFalconInstall-ubuntu"
        instances_fp :
            Path to the json file containing the instance ids, organized by region and account
            ie: { "us-east-1": { "119377359737": ["i-0626f5871bcf77604"] } }
    """
    try:
        s3_utils = S3Utilities(
            Boto3Utilities().get_boto3_client(
                account=ACCOUNT, client_type="s3", role_name=ROLE
            )
        )
        with open(
            instances_fp,
            "r",
            encoding="utf-8",
        ) as read_file:
            instances_list = read_file.read()
            s3_utils.put_object_(
                data=instances_list,
                bucket=S3_BUCKET,
                key="ssm_tool/run_document/instance_list",
            )
        presignedurl = s3_utils.get_presigned_url(
            bucket=INSTALLS_BUCKET, key=f"crowdstrike-installs/{install}"
        )
        event = {
            "action": "init",
            "instance_list": "ssm_tool/run_document/instance_list",
            "args": {
                "document": document,
                "parameters": {"presignedurl": [presignedurl], "activate": ["False"]},
            },
        }
        res = start_state_machine.main(
            stage=STAGE,
            call="run_document",
            name="test",
            input_string=json.dumps(event),
            wait=True,
        )
        return res
    except Exception as ex:  # pylint: disable=broad-except
        msg = f"Exception caught in install_crowdstrike\ntype: {ex.__class__.__name__} : {ex}"
        print(msg)
        raise Exception(msg) from ex


def main(
    stage: str, install_version: str, document_name: str, instances_path: str
) -> str:
    """Entrypoint function"""
    # TODO would be more functional to be able to pass in the distro and arch then use a dict to look up the document and install_name
    # TODO Build prod functionality
    print(stage)
    trigger_crowdstrike_install(
        install=install_version, document=document_name, instances_fp=instances_path
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("env", help="The ci stage, generally 'dev' or 'prod'")
    parser.add_argument(
        "install_version", help="Name of the cloudstrike install, OS specific"
    )
    parser.add_argument(
        "document_name", help="Name of the install Document, OS specific"
    )
    parser.add_argument(
        "instances_path",
        help="path to the Json file representing the list of instances to install",
    )
    args = parser.parse_args()
    print(args)
    print(
        main(
            stage=args.env,
            install_version=args.install_version,
            document_name=args.document_name,
            instances_path=args.instances_path,
        )
    )

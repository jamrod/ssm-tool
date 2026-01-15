"""Start execution on an AMI pipleine state machine"""
import argparse
from log_it import get_logger, log_it
from layers.utilities.aws.boto3_utilities import Boto3Utilities
from layers.utilities.aws.ssm_utilities import SsmUtilities


DEV_ACCOUNT = "account1"
PROD_ACCOUNT = "account2"
ROLE_NAME = "PCMCloudAdmin"
LOGGER = get_logger("LOG_LEVEL", "info")


@log_it
def create_or_update(
    ssm_utils: SsmUtilities, name: str, doc_path: str, doc_format: str
) -> bool:
    """Create a document or update an existing document
    Parameters
    ---------
    ssm_utils : SsmUtilities
        SSM Boto 3 Client
    name : str
        The name of the document, must be unique
    doc_path : str
        The path to the .json .yaml file containing the document
    doc_format : str
        JSON or YAML
    """
    with open(doc_path, "r", encoding="utf-8") as r_file:
        content = r_file.read()
    res = ssm_utils.get_document(name=name)
    if res:
        ssm_utils.update_document_set_default(
            name=name, content=content, doc_format=doc_format.upper()
        )
        return True
    ssm_utils.create_command_document(
        name=name, content=content, doc_format=doc_format.upper()
    )
    return "success"


def main(stage: str, name: str, doc_path: str) -> str:
    """Entrypoint function
    Parameters
        ---------
        stage : str
            The ci stage
        name : str
            The name to apply to the run
        doc_path : str
            The path to the .json .yaml file containing the document
        doc_format : str
            JSON or YAML

        Returns
        -------
        str
    """
    account = DEV_ACCOUNT
    if stage == "PRD":
        account = PROD_ACCOUNT
    ssm_utils = SsmUtilities(
        Boto3Utilities().get_boto3_client(account, "ssm", ROLE_NAME)
    )
    if doc_path.lower().endswith(".json"):
        doc_type = "JSON"
    elif doc_path.lower().endswith(".yml") or doc_path.lower().endswith(".yaml"):
        doc_type = "YAML"
    else:
        return "Invalid Document format, must be yaml or json"
    res = create_or_update(
        ssm_utils=ssm_utils, name=name, doc_path=doc_path, doc_format=doc_type
    )
    return "success" if res else "failed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("env", help="The ci stage, generally 'DEV' or 'PRD'")
    parser.add_argument("name", help="name for the execution")
    parser.add_argument("doc_path", help="path to the document")
    args = parser.parse_args()
    print(args)
    print(main(stage=args.env, name=args.name, doc_path=args.doc_path))

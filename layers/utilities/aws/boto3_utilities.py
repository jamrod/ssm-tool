# pylint: disable=too-many-public-methods
"""Module for getting boto3 clients and aws regions"""
import os
import re
from typing import Any, Dict, List
import boto3  # type: ignore
from botocore import config as CONFIG  # type: ignore
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get("LOG_LEVEL", "info"))
INITIAL_ACCT_ROLE = os.environ.get("INITIAL_ACCT_ROLE", "OrganizationAccountAccessRole")
DEFAULT_REGION = os.environ.get("DEFAULT_REGION", "us-east-1")
STS_ROLE_NAME = os.environ.get("STS_ROLE_NAME", "PCMCloudAdmin")


class Boto3Utilities:
    """Utilities class used primarily to get boto3 clients
    and a list of aws regions.
    """

    DEFAULT_STS_ROLE_NAME = STS_ROLE_NAME

    default_config = CONFIG.Config(
        retries=dict(max_attempts=10)  # docs say default is 5
    )

    default_region = DEFAULT_REGION

    region_map = {
        "af-south-1": "Africa (Cape Town)",
        "ap-east-1": "Asia Pacific (Hong Kong)",
        "ap-northeast-1": "Asia Pacific (Tokyo)",
        "ap-northeast-2": "Asia Pacific (Seoul)",
        "ap-northeast-3": "Asia Pacific (Osaka-Local)",
        "ap-south-1": "Asia Pacific (Mumbai)",
        "ap-southeast-1": "Asia Pacific (Singapore)",
        "ap-southeast-2": "Asia Pacific (Sydney)",
        "ca-central-1": "Canada (Central)",
        "cn-north-1": "China (Beijing)",
        "cn-northwest-1": "China (Ningxia)",
        "eu-central-1": "EU (Frankfurt)",
        "eu-north-1": "EU (Stockholm)",
        "eu-south-1": "Europe (Milan)",
        "eu-west-1": "EU (Ireland)",
        "eu-west-2": "EU (London)",
        "eu-west-3": "EU (Paris)",
        "me-south-1": "Middle East (Bahrain)",
        "sa-east-1": "South America (Sao Paulo)",
        "us-east-1": "US East (N. Virginia)",
        "us-east-2": "US East (Ohio)",
        "us-gov-east-1": "AWS GovCloud (US-East)",
        "us-gov-west-1": "AWS GovCloud (US)",
        "us-west-1": "US West (N. California)",
        "us-west-2": "US West (Oregon)",
    }

    def __init__(self, sts_role_name: str = None, config: CONFIG.Config = None) -> None:
        """Intitializes an Boto3Utilities object

        Parameters
        ----------
        sts_role_name : str
            The name of the role to assume if different
            from Boto3Utilities.DEFAULT_STS_ROLE_NAME
            Default: Boto3Utilities.DEFAULT_STS_ROLE_NAME

        config : Config
            The botocore.config.Config to use. This
            allows overriding retries, connection
            timeouts, etc.
            Default: Boto3Utilities.default_config

        DOCTESTS
        --------
        >>> utilities = Boto3Utilities()
        >>> bool(utilities.get_sts_role_name() == Boto3Utilities.DEFAULT_STS_ROLE_NAME)
        True
        >>> utilities = Boto3Utilities(sts_role_name='managed-role/PearsonAdmin')
        >>> bool(utilities.get_sts_role_name() == 'managed-role/PearsonAdmin')
        True
        """
        self.sts_role_name = sts_role_name
        if config is None:
            config = Boto3Utilities.default_config
        self.config = config

    def get_sts_role_name(self) -> str:
        """Getter for the sts_role_name property"""
        return self._sts_role_name

    def set_sts_role_name(self, sts_role_name: str) -> None:
        """Setter for the sts_role_name property, which allows
        the role to be set first in the account_dict and then
        default to this module's STS_ROLE_NAME, which can be
        overridden by an envrionment variable.
        """
        role_name = sts_role_name
        if role_name is None:
            role_name = Boto3Utilities.DEFAULT_STS_ROLE_NAME
        self._sts_role_name = (role_name)  # pylint: disable=attribute-defined-outside-init

    sts_role_name = property(get_sts_role_name, set_sts_role_name)

    def get_method_sts_role_name(self, role_name) -> str:
        """Return the name of the role to assume, which defaults to
        Boto3Utilities.DEFAULT_STS_ROLE_NAME, but can be overridden by
        passing the role name as an STS_ROLE_NAME envrionment variable
        or by passing the role name in as an arg to Boto3Utilities
        __init__ method.

        Parameters
        ----------
        role_name : str
            The name of the role

        Returns
        -------
        str
            the name of the role to assume, which will default to
            Boto3Utilities.DEFAULT_STS_ROLE_NAME, which can be overridden by
            passing the role name an envrionment variable
        """
        if role_name:
            return role_name
        return self.get_sts_role_name()

    @log_it
    def get_region_list(self, account: str) -> List[str]:
        """Return the list of enabled regions for the given account"""
        try:
            ec2_client = self.get_boto3_client(
                account=account, client_type="ec2", role_name=STS_ROLE_NAME
            )
        except Exception as ex:  # pylint: disable=broad-except
            raise ex
        regions = [
            region["RegionName"]
            for region in ec2_client.describe_regions(AllRegions=False)["Regions"]
        ]
        regions.sort()
        return regions

    @staticmethod
    def get_region_map() -> Dict[str, str]:
        """Return the hard-coded list of regions
        with their names
        """
        return Boto3Utilities.region_map

    @staticmethod
    def get_region_name(region: str) -> str:
        """Return the name of the region.
        Example: us-east-1 = US East (N. Virginia)

        DOCTESTS
        --------
        >>> Boto3Utilities.enabled_regions['us-east-1']
        'US East (N. Virginia)'
        >>> Boto3Utilities.enabled_regions['ap-south-1']
        'Asia Pacific (Mumbai)'
        >>> Boto3Utilities.enabled_regions['eu-west-3']
        'EU (Paris)'
        """
        return Boto3Utilities.region_map[region]

    @staticmethod
    def get_global_region() -> str:
        """Return 'us-east-1'"""
        return "us-east-1"

    @log_it
    def get_boto3_client_with_current_role(
        self, client_type: str, region: str = DEFAULT_REGION, endpoint_url: str = None
    ) -> Any:
        """Return a boto3.Session().client of the requested type
        without switching to a different role

        Parameters
        ----------
        client_type : str
            The boto3 client type, like ec2, ses, sns, etc.

        region : str
            The aws region for the client
            Default: DEFAULT_REGION

        endpoint_url : str
            An optional endpoint url to use when creating the client

        Returns
        -------
        Any
            A boto3.Session().client of the requested type
        """
        session = boto3.Session()
        if endpoint_url:
            return session.client(
                service_name=client_type,
                region_name=region,
                endpoint_url=endpoint_url,
                config=self.config,
            )
        return session.client(
            service_name=client_type, region_name=region, config=self.config
        )

    @log_it
    def get_boto3_resource_with_current_role(
        self, resource_type: str, region: str = DEFAULT_REGION, endpoint_url: str = None
    ) -> Any:
        """Return a boto3.Session().resource of the requested type
        without switching to a different role

        Parameters
        ----------
        resource_type : str
            The boto3 resource type, like s3

        region : str
            The aws region for the client
            Default: DEFAULT_REGION

        endpoint_url : str
            An optional endpoint url to use when creating the client

        Returns
        -------
        Any
            A boto3.Session().client of the requested type
        """
        session = boto3.Session()
        if endpoint_url:
            return session.client(
                service_name=resource_type,
                region_name=region,
                endpoint_url=endpoint_url,
                config=self.config,
            )
        return session.resource(
            service_name=resource_type, region_name=region, config=self.config
        )

    @log_it
    def get_boto3_client(
        self,
        account: str,
        client_type: str,
        role_name: str = None,
        region: str = DEFAULT_REGION,
        endpoint_url: str = None,
    ) -> Any:  # pylint: disable=too-many-arguments
        """Return a boto3.client(client_type) for the given account,
        role_name, region, and client_type combination. This will get
        and use credentials for the given account/role combo to create
        the client.

        Parameters
        ----------
        account : str
            The id of the aws account in which the client should be created

        client_type : str
            The boto3 client type, like ec2, ses, sns, etc.

        role_name : str
            The name of the role to assume

        region : str
            The aws region for the client
            Default: DEFAULT_REGION

        endpoint_url : str
            An optional endpoint url to use when creating the client

        Returns
        -------
        Any
            A boto3.Session().client of the requested type that was
            created using assume role credentials for the given
            account/role combo
        """
        creds = self._get_assume_role_credentials(account, role_name)
        if endpoint_url:
            return boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=region,
            ).client(
                service_name=client_type,
                region_name=region,
                endpoint_url=endpoint_url,
                config=self.config,
            )
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region,
        ).client(service_name=client_type, region_name=region, config=self.config)

    @log_it
    def get_boto3_resource(
        self,
        account: str,
        resource_type: str,
        role_name: str = None,
        region: str = DEFAULT_REGION,
        endpoint_url: str = None,
    ) -> Any:  # pylint: disable=too-many-arguments
        """Return a boto3.resource(resource_type) for the given account,
        role_name, region, and resource_type combination

        Parameters
        ----------
        account : str
            The id of the aws account in which the client should be created

        resource_type : str
            The boto3 resource type, like iam, s3 etc.

        role_name : str
            The name of the role to assume

        region : str
            The aws region for the resource
            Default: DEFAULT_REGION

        endpoint_url : str
            An optional endpoint url to use when creating the resource

        Returns
        -------
        Any
            A boto3.Session().resource of the requested type that was
            created using assume role credentials for the given
            account/role combo
        """
        creds = self._get_assume_role_credentials(
            account, self.get_method_sts_role_name(role_name)
        )
        if endpoint_url:
            return boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=region,
            ).resource(
                service_name=resource_type,
                region_name=region,
                endpoint_url=endpoint_url,
                config=self.config,
            )
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region,
        ).resource(service_name=resource_type, region_name=region, config=self.config)

    @log_it
    def get_new_acct_client(
        self,
        client_type: str,
        payer_account: str,
        account: str,
        payer_role: str = None,
        account_role: str = INITIAL_ACCT_ROLE,
        region: str = DEFAULT_REGION,
        endpoint_url: str = None,
    ) -> Any:  # pylint: disable=too-many-arguments
        """Facilitate the first steps of account creation
        where the credentials from the master payer are used to assume
        the OrganizationAccountAccessRole in the new account.

        IT IS UNLIKELY THAT THIS IS THE METHOD YOU NEED.
        The get_boto3_client methods should almost always be used
        instead of this.

        Parameters
        ----------
        client_type : str
            The boto3 client type

        payer_account : str
            The aws account id of the master payer: 150047381276
            or 958342668309

        account : str
            The aws account id of the newly created account

        payer_role : str
            The role to assume in the master payer
            Default: STS_ROLE_NAME

        account_role : str
            The role to assume in the newly created account
            Default: INITIAL_ACCT_ROLE

        region : str
            The aws region in which the boto3 client should
            be created
            Default: us-east-1

        endpoint_url : str
            An optional endpoint url to use when creating the client

        Returns
        -------
        Any
            A boto3.Session().client of the requested type for the given
            account created from a session out of the payer_account
        """
        try:
            creds = self._get_assume_role_credentials(payer_account, payer_role)
            creds = self._get_assume_role_credentials(account, account_role, creds)
            if endpoint_url:
                return boto3.client(
                    service_name=client_type,
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                    region_name=region,
                    endpoint_url=endpoint_url,
                    config=self.config,
                )
            return boto3.client(
                service_name=client_type,
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=region,
                config=self.config,
            )
        except Exception as ex:
            LOGGER.error(
                f"Exception encounterd in get_payer_to_new_acct_cloudformation_client: {ex}"
            )
            raise ex

    @log_it
    def _get_assume_role_credentials(
        self, account: str, role_name: str, from_credentials: dict = None
    ):
        """Return the assumed role credentials after assuming the
        given role in the given account, using the from_credentials
        to first create a session if it was provided.

        Parameters
        ----------
        account : str
            The aws account id of the account in which the
            role should be assumed, like 431588932716

        role_name : str
            The name of the role to assume, like PearsonCloudAmin

        from_credentials : dict
            A Credentials object to use when assuming the role
            Default: None

        Returns
        -------
        dict
            The Credentials portion of the boto3.sts.assume_role
            response, which has the following sturcture:

            {
                'AccessKeyId': 'string',
                'SecretAccessKey': 'string',
                'SessionToken': 'string',
                'Expiration': datetime(2015, 1, 1)
            }

        """
        result = {}
        # Call the assume_role method of the STSConnection object and pass the role
        # ARN and a role session name.
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
        session_name = self._get_session_name(account, role_name)
        try:
            # Get the sts client. Use from_credentials if specified
            if from_credentials is None:
                sts_client = boto3.client("sts", config=self.config)
            else:
                session = boto3.Session(
                    aws_access_key_id=from_credentials["AccessKeyId"],
                    aws_secret_access_key=from_credentials["SecretAccessKey"],
                    aws_session_token=from_credentials["SessionToken"],
                )
                sts_client = session.client("sts", config=self.config)

            assumed_role_object = sts_client.assume_role(
                RoleArn=role_arn, RoleSessionName=session_name
            )
            result = assumed_role_object["Credentials"]
        except Exception as ex:
            LOGGER.error(f"Failed to assume {role_arn} in {account}")
            raise ex
        return result

    @staticmethod
    def _get_session_name(account: str, role_name: str) -> str:
        """Make sure the session name is valid, and change it if not"""
        session_name = f"{account}-{role_name}-session".replace("/", "-")
        matches = re.match("([\\w+=,.@-]*)", session_name)
        if matches:
            return session_name
        return f"{account}-session"

    def __repr__(self):
        """Return a string representation of the object"""
        return "Boto3Utilities()"


def main():
    """Support for local execution"""
    # aws-runas governator py -m shared.aws.boto3_utilities
    boto3_utils = Boto3Utilities()
    LOGGER.info(boto3_utils)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    # main()

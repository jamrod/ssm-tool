"""Module for interacting with S3 via Boto3"""
import json
import os
import yaml
from boto3_type_annotations.s3 import client as s3Client  # type: ignore
from log_it import get_logger, log_it


LOGGER = get_logger(os.path.basename(__file__), os.environ.get("LOG_LEVEL", "info"))


class S3Utilities:
    """Methods for interacting with Boto3 aws s3 client"""

    def __init__(self, client: s3Client) -> None:
        """Initialize an S3Utilities object"""
        self.client = client

    @log_it
    def get_object_as_string(self, bucket: str, key: str) -> str:
        """Get an object from s3 as plain text

        Parameters
        ---------
        bucket : str
            S3 bucket
        key : str
            The key of the object to fetch from the bucket

        Returns
        -------
        str

        """
        output = ""
        try:
            res = self.client.get_object(Bucket=bucket, Key=key)
            output = res["Body"].read().decode("utf-8")
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception occured in get_object_as_string {bucket}/{key} \n{ex}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return output

    @log_it
    def list_bucket_keys(self, bucket: str, prefix: str = "") -> list:
        """Return a list of keys contained in bucket

        Parameters
        ----------
        bucket : str
            The name of the bucket
        prefix : str (optional)
            return results with given prefix

        Returns
        -------
        list
            list of keys as dicts {'Key': key}
        """
        paginator = self.client.get_paginator("list_objects_v2")
        output = []
        try:
            res = paginator.paginate(
                Bucket=bucket,
                Prefix=prefix,
            )
            for page in res:
                if "Contents" in page.keys():
                    for item in page["Contents"]:
                        if item["Key"] != prefix:
                            output.extend([{"Key": item["Key"]}])
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception occured in list_bucket_keys on {bucket}/{prefix} \n{ex}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return output

    @log_it
    def delete_objects_(self, bucket: str, keys: list) -> None:
        """Deletes multiple items from bucket
        max keys that can be deleted in one call is 1000

        Parameters
        ----------
        bucket : str
            The name of the bucket
        keys : List
            The list of keys to delete, formatted as dicts, {'Key': key}
        """
        limit = 1000
        if keys:
            chunked_keys = [keys[i: i + limit] for i in range(0, len(keys), limit)]
            try:
                for keys_chunk in chunked_keys:
                    self.client.delete_objects(
                        Bucket=bucket, Delete={"Objects": keys_chunk}
                    )
            except Exception as ex:  # pylint: disable=broad-except
                msg = f"Exception occured in delete_objects_ in {bucket} \n{ex}"
                LOGGER.error(msg)
                raise Exception(msg) from ex

    @log_it
    def put_object_(self, data: str, bucket: str, key: str) -> None:
        """Post data to s3 bucket

        Parameters
        ----------
        data : str
            string of data to be saved to s3

        bucket : str
            S3 bucket to save data to

        key : str
            S3 key to save data to

        """
        body = bytes(data.encode("UTF-8"))
        try:
            self.client.put_object(Bucket=bucket, Key=key, Body=body)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception occured in put_object {bucket}/{key} \n{ex}"
            LOGGER.error(msg)
            raise Exception(msg) from ex

    @log_it
    def get_object_as_dict(self, bucket: str, key: str) -> dict:
        """Get an object from s3, will also return a List if that's what the object is

        Parameters
        ---------
        bucket : str
            S3 bucket
        key : str
            The key of the object to fetch from the bucket

        Returns
        -------
        dict

        """
        output = {}
        try:
            res = self.client.get_object(Bucket=bucket, Key=key)
            data = res["Body"].read().decode("utf-8")
            output = json.loads(data)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception occured in get_object_as_dict for {bucket}/{key} \n{ex}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return output

    @log_it
    def get_yaml_object_as_dict(self, bucket: str, key: str) -> dict:
        """Get an object from s3

        Parameters
        ---------
        bucket : str
            S3 bucket
        key : str
            The key of the object to fetch from the bucket

        Returns
        -------
        dict

        """
        output = {}
        try:
            res = self.client.get_object(Bucket=bucket, Key=key)
            data = res["Body"].read().decode("utf-8")
            output = yaml.load(data, Loader=yaml.FullLoader)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception occured in get_yaml_object_as_dict {bucket}/{key} \n{ex}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return output

    @log_it
    def get_presigned_url(self, bucket: str, key: str, expiry: int = 3600) -> str:
        """Get a presigned url for an object on s3

        Parameters
        ---------
        bucket : str
            S3 bucket
        key : str
            The key of the object to create a url for
        expiry : int
            The number of seconds the url will be valid for defaults to 3600 = 1 hour

        Returns
        -------
        str

        """
        url = ""
        try:
            url = self.client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiry)
        except Exception as ex:  # pylint: disable=broad-except
            msg = f"Exception occured in getpresigned_url\n{ex.__class__.__name__}: {str(ex)}"
            LOGGER.error(msg)
            raise Exception(msg) from ex
        return url


def main():
    """support for local testing"""
    print(__doc__)


if __name__ == "__main__":
    main()

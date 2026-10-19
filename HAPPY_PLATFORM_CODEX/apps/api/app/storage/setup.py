from botocore.exceptions import ClientError

from app.core.config import settings
from app.storage.s3 import check_object_storage, get_storage_client


def setup_bucket() -> None:
    client = get_storage_client()
    try:
        check_object_storage()
    except ClientError as exc:
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise
        client.create_bucket(Bucket=settings.s3_bucket, ACL="private")
    check_object_storage()


if __name__ == "__main__":
    setup_bucket()
    print("Private application bucket is ready.")

import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from app.core.config import settings
from app.storage.s3 import get_storage_client
from app.storage.setup import setup_bucket


def test_missing_bucket_is_created_private() -> None:
    with Stubber(get_storage_client()) as stub:
        stub.add_client_error("head_bucket", service_error_code="404", http_status_code=404)
        stub.add_response("create_bucket", {}, {"Bucket": settings.s3_bucket, "ACL": "private"})
        stub.add_response("head_bucket", {}, {"Bucket": settings.s3_bucket})
        setup_bucket()
        stub.assert_no_pending_responses()


def test_access_denied_does_not_create_bucket() -> None:
    with Stubber(get_storage_client()) as stub:
        stub.add_client_error(
            "head_bucket", service_error_code="AccessDenied", http_status_code=403
        )
        with pytest.raises(ClientError):
            setup_bucket()
        stub.assert_no_pending_responses()

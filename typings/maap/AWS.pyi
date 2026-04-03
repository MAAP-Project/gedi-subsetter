from typing import Mapping, TypedDict

class AWSCredentials(TypedDict):
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str

class AWSRequesterPaysCredentials(TypedDict):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_session_token: str

class AWS:
    def __init__(
        self,
        requester_pays_endpoint: str,
        s3_signed_url_endpoint: str,
        earthdata_s3_credentials_endpoint: str,
        workspace_bucket_endpoint: str,
        api_header: Mapping[str, str],
    ): ...
    def earthdata_s3_credentials(self, endpoint_uri: str) -> AWSCredentials: ...
    def requester_pays_credentials(
        self, expiration: int = ...
    ) -> AWSRequesterPaysCredentials: ...

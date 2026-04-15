from typing import Mapping, TypedDict

class AWSCredentials(TypedDict):
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str
    expiration: str  # Example: "2026-04-09 20:38:01+00:00"

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

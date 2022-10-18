from typing import Mapping, TypedDict

class AWSCredentials(TypedDict):
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str

class AWS:
    def __init__(
        self,
        requester_pays_endpoint: str,
        s3_signed_url_endpoint: str,
        earthdata_s3_credentials_endpoint: str,
        api_header: Mapping[str, str],
    ): ...
    def earthdata_s3_credentials(self, endpoint_uri: str) -> AWSCredentials: ...

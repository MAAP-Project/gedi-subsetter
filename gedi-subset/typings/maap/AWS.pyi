from typing import TypedDict

class AWSCredentials(TypedDict):
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str

class AWS:
    def earthdata_s3_credentials(self, endpoint_uri: str) -> AWSCredentials: ...

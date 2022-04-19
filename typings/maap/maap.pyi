from typing import Sequence

from .AWS import AWS
from .Result import Collection, Granule

class MAAP:
    aws: AWS

    def __init__(self, maap_host: str = ...): ...
    def searchCollection(self, limit: int = ..., **kwargs) -> Sequence[Collection]: ...
    def searchGranule(self, limit: int = ..., **kwargs) -> Sequence[Granule]: ...

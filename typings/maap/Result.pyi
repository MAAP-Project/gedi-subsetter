from typing import Optional

class Result(dict):
    def getData(self, destpath: str = ..., overwrite: bool = ...) -> str: ...
    def getDownloadUrl(self) -> Optional[str]: ...

class Collection(Result): ...

class Granule(Result):
    _downloadname: Optional[str]

from pydantic import BaseModel


class Finding(BaseModel):
    type: str
    match: str
    offset: int
    length: int
    line: int
from pydantic import BaseModel


class SelfUserResponse(BaseModel):
    name: str
    email: str

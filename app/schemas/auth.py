from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    full_name: str = Field(min_length=2, max_length=160)
    document_number: str = Field(min_length=4, max_length=40)
    phone: str = Field(min_length=6, max_length=40)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    document_number: str
    phone: str
    is_active: bool
    role: str


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

from pydantic import BaseModel


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None


class LogoutResponse(BaseModel):
    message: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str

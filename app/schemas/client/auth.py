from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator

# ==================== 注册相关 ====================


class SendVerificationCode(BaseModel):
    """发送验证码请求"""

    email: EmailStr = Field(..., description="邮箱地址")


class RegisterWithCode(BaseModel):
    """验证码注册请求"""

    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, description="密码（至少8位）")
    verification_code: str = Field(
        ..., min_length=6, max_length=6, description="6位验证码"
    )
    first_name: Optional[str] = Field(None, max_length=100, description="名字")
    last_name: Optional[str] = Field(None, max_length=100, description="姓氏")

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少为8位")
        return v


# ==================== 登录相关 ====================


class Login(BaseModel):
    """邮箱密码登录请求"""

    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")


class GoogleLogin(BaseModel):
    """Google SSO登录请求"""

    id_token: str = Field(..., description="Google ID Token")


class Token(BaseModel):
    """Token响应"""

    access_token: str
    refresh_token: str
    token_type: str
    user: Optional[dict] = None  # 注册时返回用户信息


class RefreshToken(BaseModel):
    """刷新token请求"""

    refresh_token: str = Field(..., description="刷新令牌")


class Logout(BaseModel):
    """登出请求"""

    refresh_token: str = Field(..., description="刷新令牌")


# ==================== 密码重置 ====================


class RequestPasswordReset(BaseModel):
    """请求密码重置"""

    email: EmailStr = Field(..., description="邮箱地址")


class ResetPassword(BaseModel):
    """重置密码"""

    token: str = Field(..., description="重置token")
    new_password: str = Field(..., min_length=8, description="新密码（至少8位）")

    @validator("new_password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少为8位")
        return v


# ==================== 响应 ====================


class MessageResponse(BaseModel):
    """通用消息响应"""

    message: str

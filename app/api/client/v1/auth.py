from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import (ClientAuthService, get_client_auth_service,
                                 get_redis)
from app.db.session import get_db
from app.schemas.client.auth import (GoogleLogin, Login, Logout,
                                     MessageResponse, RefreshToken,
                                     RegisterWithCode, RequestPasswordReset,
                                     ResetPassword, SendVerificationCode,
                                     Token)
from app.schemas.response import ApiResponse
from app.services.common.redis import RedisClient

router = APIRouter()


# ==================== 注册相关 ====================


@router.post("/send-verification-code", response_model=MessageResponse)
async def send_verification_code(
    request: SendVerificationCode,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    发送注册验证码

    - 检查邮箱是否已注册
    - 生成6位数字验证码
    - 5分钟有效期，60秒发送冷却
    - 发送邮件到指定邮箱
    """
    result = await service.send_verification_code(db, redis, request.email)
    return ApiResponse.success(data=result)


@router.post("/register", response_model=Token)
async def register_with_verification_code(
    request: RegisterWithCode,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    使用验证码注册

    - 验证验证码
    - 创建用户账号
    - 自动登录返回token
    """
    result = await service.register_with_code(
        db=db,
        redis=redis,
        email=request.email,
        password=request.password,
        verification_code=request.verification_code,
        first_name=request.first_name,
        last_name=request.last_name,
    )
    return ApiResponse.success(data=result)


# ==================== 登录相关 ====================


@router.post("/login", response_model=Token)
async def login(
    request: Login,
    db: AsyncSession = Depends(get_db),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    邮箱密码登录

    - 验证邮箱和密码
    - 返回access_token和refresh_token
    """
    result = await service.login(db, request.email, request.password)
    return ApiResponse.success(data=result)


@router.post("/google-login", response_model=Token)
async def google_login(
    request: GoogleLogin,
    db: AsyncSession = Depends(get_db),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    Google SSO登录

    - 验证Google ID Token
    - 创建或更新用户账号
    - 返回access_token和refresh_token
    """
    result = await service.google_login(db, request.id_token)
    return ApiResponse.success(data=result)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshToken,
    db: AsyncSession = Depends(get_db),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    刷新访问令牌

    - 验证refresh_token
    - 返回新的access_token
    """
    result = await service.refresh_token(db, request.refresh_token)
    return ApiResponse.success(data=result)


@router.post("/logout")
async def logout(
    request: Logout,
    db: AsyncSession = Depends(get_db),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    用户登出

    - 标记refresh_token为无效
    """
    await service.logout(db, request.refresh_token)
    return ApiResponse.success_without_data()


# ==================== 密码重置 ====================


@router.post("/request-password-reset", response_model=MessageResponse)
async def request_password_reset(
    request: RequestPasswordReset,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    请求密码重置

    - 发送密码重置链接到邮箱
    - 链接30分钟有效
    - 60秒发送冷却
    """
    result = await service.request_password_reset(db, redis, request.email)
    return ApiResponse.success(data=result)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPassword,
    db: AsyncSession = Depends(get_db),
    service: ClientAuthService = Depends(get_client_auth_service),
):
    """
    重置密码

    - 验证重置token
    - 更新密码
    - 标记所有token为无效（强制重新登录）
    """
    result = await service.reset_password(db, request.token, request.new_password)
    return ApiResponse.success(data=result)

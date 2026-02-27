from datetime import UTC, datetime, timedelta
from typing import Dict, Optional

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import AuthBase
from app.db.session import transaction
from app.exceptions.http_exceptions import APIException
from app.models.token import Token
from app.models.user import User
from app.services.common.email import EmailService, get_email_service
from app.services.common.redis import RedisClient
from app.services.common.verification_code import (
    VerificationCodeService, get_verification_code_service)


class ClientAuthService(AuthBase):
    """Client authentication service"""

    def __init__(
        self,
        verification_code_service: VerificationCodeService = None,
        email_service: EmailService = None,
    ):
        """Initialize ClientAuthService with dependencies"""
        self.verification_code_service = (
            verification_code_service or VerificationCodeService()
        )
        self.email_service = email_service or EmailService()

    # ==================== Email Registration ====================

    async def send_verification_code(
        self, db: AsyncSession, redis: RedisClient, email: str
    ) -> Dict:
        """Send registration verification code"""
        # Check if email is already registered
        user_query = select(User).where(User.email == email)
        result = await db.execute(user_query)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise APIException(status_code=400, message="该邮箱已注册")

        # Generate verification code
        code = self.verification_code_service.generate_code(
            settings.VERIFICATION_CODE_LENGTH
        )

        # Store in Redis (checks cooldown period)
        await self.verification_code_service.send_verification_code(redis, email, code)

        # Send email
        await self.email_service.send_with_template(
            to_emails=email,
            template_name="auth/verification.html",
            template_params={
                "verification_code": code,
                "app_name": settings.PROJECT_NAME,
            },
            subject=f"您的验证码：{code}",
        )

        return {"message": "验证码已发送到您的邮箱"}

    async def register_with_code(
        self,
        db: AsyncSession,
        redis: RedisClient,
        email: str,
        password: str,
        verification_code: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Dict:
        """Register with verification code and auto login"""
        async with transaction(db):
            # Verify verification code
            await self.verification_code_service.verify_code(
                redis, email, verification_code
            )

            # Check if email is already registered
            user_query = select(User).where(User.email == email)
            result = await db.execute(user_query)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                raise APIException(status_code=400, message="该邮箱已注册")

            # Create user
            hashed_password = User.get_password_hash(password)
            new_user = User(
                email=email,
                hashed_password=hashed_password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_verified=True,  # Auto-mark as verified after code verification
                auth_provider="email",
            )
            db.add(new_user)
            await db.flush()

            # Generate token (auto login)
            access_token = AuthBase.create_access_token(
                str(new_user.id),
                scope="client",
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            )
            refresh_token = AuthBase.create_refresh_token(str(new_user.id))

            # 存储refresh token
            hashed_token = AuthBase.hash_token(refresh_token)
            token = Token(
                user_id=new_user.id,
                token=hashed_token,
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                is_active=True,
            )
            db.add(token)
            await db.flush()

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": {
                    "id": new_user.id,
                    "email": new_user.email,
                    "first_name": new_user.first_name,
                    "last_name": new_user.last_name,
                },
            }

    # ==================== 邮箱密码登录 ====================

    async def authenticate_user(
        self, db: AsyncSession, email: str, password: str
    ) -> Optional[User]:
        """验证用户凭据"""
        user_query = select(User).where(
            User.email == email, User.auth_provider == "email"
        )
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()

        if not user or not user.verify_password(password):
            return None
        return user

    async def login(self, db: AsyncSession, email: str, password: str) -> Dict:
        """用户登录"""
        async with transaction(db):
            user = await self.authenticate_user(db, email, password)
            if not user:
                raise APIException(status_code=400, message="邮箱或密码错误")

            if not user.is_active:
                raise APIException(status_code=400, message="账号已被禁用")

            # 标记旧token为无效
            stmt = (
                update(Token)
                .where((Token.user_id == user.id) & (Token.is_active == True))
                .values(is_active=False)
            )
            await db.execute(stmt)

            # 生成新token
            access_token = AuthBase.create_access_token(
                str(user.id),
                scope="client",
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            )
            refresh_token = AuthBase.create_refresh_token(str(user.id))

            # 存储refresh token
            hashed_token = AuthBase.hash_token(refresh_token)
            token = Token(
                user_id=user.id,
                token=hashed_token,
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                is_active=True,
            )
            db.add(token)
            await db.flush()

            # 更新最后活跃时间
            user.last_active_at = datetime.now(UTC)

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            }

    # ==================== Google SSO ====================

    async def google_login(self, db: AsyncSession, id_token_str: str) -> Dict:
        """Google SSO登录"""
        async with transaction(db):
            try:
                # Verify Google ID Token
                idinfo = id_token.verify_oauth2_token(
                    id_token_str, google_requests.Request(), settings.GOOGLE_CLIENT_ID
                )

                # 检查issuer
                if idinfo["iss"] not in [
                    "accounts.google.com",
                    "https://accounts.google.com",
                ]:
                    raise APIException(status_code=400, message="Invalid token issuer")

                google_id = idinfo["sub"]
                email = idinfo.get("email")
                first_name = idinfo.get("given_name")
                last_name = idinfo.get("family_name")
                avatar = idinfo.get("picture")

                # 查找或创建用户
                user_query = select(User).where(
                    or_(User.google_id == google_id, User.email == email)
                )
                result = await db.execute(user_query)
                user = result.scalar_one_or_none()

                if user:
                    # 更新Google ID（如果用户之前用邮箱注册）
                    if not user.google_id:
                        user.google_id = google_id
                        user.auth_provider = "google"

                    # 更新头像和姓名
                    if avatar:
                        user.avatar = avatar
                    if first_name:
                        user.first_name = first_name
                    if last_name:
                        user.last_name = last_name

                    user.last_active_at = datetime.now(UTC)
                else:
                    # Create new user
                    user = User(
                        email=email,
                        google_id=google_id,
                        first_name=first_name,
                        last_name=last_name,
                        avatar=avatar,
                        is_active=True,
                        is_verified=True,
                        auth_provider="google",
                        hashed_password="",  # Google用户无密码
                    )
                    db.add(user)
                    await db.flush()

                # 标记旧token为无效
                stmt = (
                    update(Token)
                    .where((Token.user_id == user.id) & (Token.is_active == True))
                    .values(is_active=False)
                )
                await db.execute(stmt)

                # 生成token
                access_token = AuthBase.create_access_token(
                    str(user.id),
                    scope="client",
                    expires_delta=timedelta(
                        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                    ),
                )
                refresh_token = AuthBase.create_refresh_token(str(user.id))

                # 存储refresh token
                hashed_token = AuthBase.hash_token(refresh_token)
                token = Token(
                    user_id=user.id,
                    token=hashed_token,
                    expires_at=datetime.now(UTC)
                    + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                    is_active=True,
                )
                db.add(token)
                await db.flush()

                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                }

            except ValueError as e:
                raise APIException(
                    status_code=400, message=f"Invalid Google token: {str(e)}"
                )

    # ==================== Token刷新和登出 ====================

    async def refresh_token(self, db: AsyncSession, refresh_token: str) -> Dict:
        """刷新访问令牌"""
        payload = AuthBase.verify_token(refresh_token, scope="refresh")
        if not payload:
            raise APIException(status_code=401, message="Invalid refresh token")

        user_id = int(payload.get("sub"))
        token_query = select(Token).where(
            (Token.user_id == user_id) & (Token.is_active == True)
        )
        result = await db.execute(token_query)
        token = result.scalar_one_or_none()

        if not token or not AuthBase.verify_token_hash(refresh_token, token.token):
            raise APIException(
                status_code=401, message="Invalid or expired refresh token"
            )

        token.last_used_at = datetime.now(UTC)
        await db.commit()

        access_token = AuthBase.create_access_token(
            user_id,
            scope="client",
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {"access_token": access_token, "token_type": "bearer"}

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        """User logout"""
        payload = AuthBase.verify_token(refresh_token, scope="refresh")
        if not payload:
            return  # 忽略无效token

        user_id = int(payload.get("sub"))
        token_query = select(Token).where(
            (Token.user_id == user_id) & (Token.is_active == True)
        )
        result = await db.execute(token_query)
        token = result.scalar_one_or_none()

        if token:
            token.is_active = False
            await db.commit()

    # ==================== 密码重置 ====================

    async def request_password_reset(
        self, db: AsyncSession, redis: RedisClient, email: str
    ) -> Dict:
        """Request password reset"""
        # Find user
        user_query = select(User).where(User.email == email)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            # 安全考虑：不暴露用户是否存在
            return {"message": "如果该邮箱已注册，您将收到密码重置邮件"}

        # 检查冷却时间
        cooldown_key = f"password_reset_cooldown:{email}"
        if await redis.check_cooldown(cooldown_key):
            raise APIException(
                status_code=400, message="请等待60秒后再重新发送密码重置邮件"
            )

        # 生成密码重置token（JWT）
        reset_token = AuthBase.create_access_token(
            str(user.id),
            scope="password_reset",
            expires_delta=timedelta(
                minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
            ),
        )

        # 生成重置链接
        reset_url = settings.PASSWORD_RESET_URL_TEMPLATE.format(
            frontend_url=settings.FRONTEND_URL, token=reset_token
        )

        # 发送邮件
        await self.email_service.send_with_template(
            to_emails=email,
            template_name="auth/password-reset.html",
            template_params={
                "first_name": user.first_name,
                "reset_url": reset_url,
                "app_name": settings.PROJECT_NAME,
            },
            subject="重置您的密码",
        )

        # 设置冷却时间
        await redis.set_cooldown(
            cooldown_key, settings.VERIFICATION_CODE_COOLDOWN_SECONDS
        )

        return {"message": "如果该邮箱已注册，您将收到密码重置邮件"}

    async def reset_password(
        self, db: AsyncSession, token: str, new_password: str
    ) -> Dict:
        """Reset password"""
        async with transaction(db):
            # 验证token
            payload = AuthBase.verify_token(token, scope="password_reset")
            if not payload:
                raise APIException(status_code=400, message="密码重置链接无效或已过期")

            user_id = payload.get("sub")

            # Find user
            user_query = select(User).where(User.id == int(user_id))
            result = await db.execute(user_query)
            user = result.scalar_one_or_none()

            if not user:
                raise APIException(status_code=400, message="用户不存在")

            # Update password
            user.hashed_password = User.get_password_hash(new_password)

            # 标记所有token为无效（强制重新登录）
            stmt = (
                update(Token)
                .where((Token.user_id == user.id) & (Token.is_active == True))
                .values(is_active=False)
            )
            await db.execute(stmt)

            await db.flush()

            return {"message": "密码重置成功，请使用新密码登录"}


def get_client_auth_service() -> ClientAuthService:
    """Get ClientAuthService instance (dependency injection)"""
    verification_code_service = get_verification_code_service()
    email_service = get_email_service()
    return ClientAuthService(
        verification_code_service=verification_code_service,
        email_service=email_service,
    )

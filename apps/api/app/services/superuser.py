"""Bootstrap the platform superuser from environment variables.

``SUPERUSER_EMAIL`` / ``SUPERUSER_PASSWORD`` are the source of truth: running the bootstrap (done by
``python -m app.seed`` in every deploy's pre-deploy step) creates the account, or re-asserts its admin role,
active flag and password if someone changed them. Rotating the password = change the variable and redeploy.
"""

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_password, utcnow, verify_password
from app.models import RefreshToken, User
from app.models.enums import UserRole
from app.services.audit import AuditTrail


@dataclass(frozen=True)
class BootstrapResult:
    action: str  # "created" | "updated" | "unchanged" | "skipped"
    email: str | None


async def ensure_superuser(session: AsyncSession, settings: Settings) -> BootstrapResult:
    if not (settings.superuser_email and settings.superuser_password):
        return BootstrapResult("skipped", None)
    email = settings.superuser_email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    audit = AuditTrail(session)
    if user is None:
        user = User(
            email=email,
            full_name=settings.superuser_name,
            password_hash=hash_password(settings.superuser_password),
            role=UserRole.platform_admin,
        )
        session.add(user)
        await session.flush()
        audit.record(user.id, "superuser.bootstrap_create", "user", user.id)
        await session.commit()
        return BootstrapResult("created", email)

    changed: list[str] = []
    if user.role != UserRole.platform_admin:
        user.role = UserRole.platform_admin
        changed.append("role")
    if not user.is_active:
        user.is_active = True
        changed.append("is_active")
    if not verify_password(user.password_hash, settings.superuser_password):
        user.password_hash = hash_password(settings.superuser_password)
        changed.append("password")
        # A rotated password must also end existing sessions.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
    if not changed:
        return BootstrapResult("unchanged", email)
    audit.record(user.id, "superuser.bootstrap_update", "user", user.id, data={"fields": changed})
    await session.commit()
    return BootstrapResult("updated", email)

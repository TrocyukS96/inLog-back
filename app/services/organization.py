from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationCreate


async def list_user_organizations(db: AsyncSession, user: User) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at.desc())
    )
    return list(result.scalars().unique().all())


async def get_user_organization(
    db: AsyncSession,
    user: User,
    organization_id: int,
) -> Organization | None:
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember)
        .where(
            Organization.id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    return result.scalar_one_or_none()


async def create_organization(
    db: AsyncSession,
    user: User,
    data: OrganizationCreate,
) -> Organization:
    organization = Organization(
        full_name=data.full_name,
        short_name=data.short_name,
        address=data.address,
        inn=data.inn,
        kpp=data.kpp,
    )
    db.add(organization)
    await db.flush()

    db.add(
        OrganizationMember(
            user_id=user.id,
            organization_id=organization.id,
            role="admin",
        )
    )
    await db.flush()
    await db.refresh(organization)
    return organization


async def delete_organization(db: AsyncSession, organization: Organization) -> None:
    await db.delete(organization)

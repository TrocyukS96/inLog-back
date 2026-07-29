from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationRead
from app.services.organization import (
    create_organization,
    delete_organization,
    get_user_organization,
    list_user_organizations,
)

router = APIRouter(prefix="/organizations/organization", tags=["organizations"])


@router.get("/", response_model=list[OrganizationRead])
async def get_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationRead]:
    organizations = await list_user_organizations(db, current_user)
    return [OrganizationRead.model_validate(org) for org in organizations]


@router.post("/", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def add_organization(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    organization = await create_organization(db, current_user, data)
    return OrganizationRead.model_validate(organization)


@router.delete("/{organization_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def remove_organization(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    organization = await get_user_organization(db, current_user, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    await delete_organization(db, organization)

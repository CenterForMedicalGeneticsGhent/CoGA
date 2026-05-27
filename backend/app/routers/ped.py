from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.postgres import get_postgres_session
from ..dependencies import get_current_admin_user, get_current_user
from ..schemas import ManualPedFamilyCreate, PedUploadResult
from ..services.metadata_service import CurrentUser
from ..services.ped_service import create_manual_family_data, upload_ped_data

router = APIRouter(prefix="/ped", tags=["ped"])


@router.post("/upload", response_model=PedUploadResult)
async def upload_ped(
    file: UploadFile = File(...),
    overwrite: bool = False,
    project_id: str | None = None,
    roi_query: str | None = Form(default=None),
    inheritance_model: str | None = Form(default=None),
    obligate_carriers: str | None = Form(default=None),
    proven_carriers: str | None = Form(default=None),
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_admin_user),
):
    return await upload_ped_data(
        session,
        file,
        overwrite,
        user,
        project_id,
        roi_query=roi_query,
        inheritance_model=inheritance_model,
        obligate_carriers=obligate_carriers,
        proven_carriers=proven_carriers,
    )


@router.post("/manual", response_model=PedUploadResult)
async def create_manual_family(
    family: ManualPedFamilyCreate,
    overwrite: bool = False,
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
):
    return await create_manual_family_data(session, family, overwrite, user)

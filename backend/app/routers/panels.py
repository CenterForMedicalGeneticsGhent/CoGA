from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.postgres import get_postgres_session
from ..dependencies import (
    get_current_user,
)
from ..schemas import (
    GenePanelOut,
    GenePanelCreate,
    GenePanelCreateResponse,
    PanelAppImportRequest,
    PanelAppImportResponse,
    PanelAppPanelSearchResponse,
)
from ..services.metadata_service import CurrentUser
from ..services.panel_metadata_service import (
    create_panel_data,
    delete_panel_data,
    get_panel_or_404,
    import_panelapp_panel_data,
    list_panels_data,
)
from ..services.panelapp_service import search_panelapp_panels

router = APIRouter(prefix="/panels", tags=["panels"])


@router.get("/", response_model=List[GenePanelOut])
async def list_panels(
    session: AsyncSession = Depends(get_postgres_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[GenePanelOut]:
    return await list_panels_data(session)


@router.get("/panelapp/search", response_model=PanelAppPanelSearchResponse)
async def search_panelapp(
    query: str = Query("", max_length=120),
    page_size: int = Query(20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
) -> PanelAppPanelSearchResponse:
    del current_user
    results, count = await search_panelapp_panels(query, page_size=page_size)
    return PanelAppPanelSearchResponse(results=results, count=count)


@router.post("/import/panelapp", response_model=PanelAppImportResponse, status_code=201)
async def import_panelapp_panel(
    request: PanelAppImportRequest,
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> PanelAppImportResponse:
    return await import_panelapp_panel_data(session, request, user)


@router.get("/{panel_id}", response_model=GenePanelOut)
async def get_panel(
    panel_id: str,
    session: AsyncSession = Depends(get_postgres_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> GenePanelOut:
    return await get_panel_or_404(session, panel_id)


@router.post("/", response_model=GenePanelCreateResponse, status_code=201)
async def create_panel(
    panel: GenePanelCreate,
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> GenePanelCreateResponse:
    return await create_panel_data(session, panel, user)


@router.delete("/{panel_id}", status_code=204)
async def delete_panel(
    panel_id: str,
    session: AsyncSession = Depends(get_postgres_session),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    await delete_panel_data(session, panel_id, user)

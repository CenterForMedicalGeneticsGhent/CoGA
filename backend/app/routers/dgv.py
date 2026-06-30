from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.postgres import get_postgres_session
from ..dependencies import get_current_user
from ..schemas import DgvTrackOut
from ..services.reference_metadata_service import get_dgv_track_data

# Reference data requires authentication (a router-level dependency gates every
# endpoint, including any added later).
router = APIRouter(prefix="/dgv", tags=["dgv"], dependencies=[Depends(get_current_user)])


@router.get("/{assembly}/{chrom}", response_model=DgvTrackOut)
async def get_dgv_track(
    assembly: str,
    chrom: str,
    start: int = Query(0, ge=0),
    end: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_postgres_session),
) -> DgvTrackOut:
    return await get_dgv_track_data(
        session,
        assembly=assembly,
        chrom=chrom,
        start=start,
        end=end,
    )

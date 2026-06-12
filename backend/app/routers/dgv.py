from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.postgres import get_postgres_session
from ..schemas import DgvTrackOut
from ..services.reference_metadata_service import get_dgv_track_data

router = APIRouter(prefix="/dgv", tags=["dgv"])


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

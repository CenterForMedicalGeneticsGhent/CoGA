from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.postgres import get_postgres_session
from ..dependencies import get_current_user
from ..schemas import SegmentalDuplicationOut
from ..services.reference_metadata_service import get_segmental_duplications_data

# Reference data requires authentication (a router-level dependency gates every
# endpoint, including any added later).
router = APIRouter(
    prefix="/segmental-duplications",
    tags=["segmental_duplications"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/{assembly}/{chrom}", response_model=List[SegmentalDuplicationOut])
async def get_segmental_duplications(
    assembly: str,
    chrom: str,
    start: int = Query(0, ge=0),
    end: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_postgres_session),
) -> List[SegmentalDuplicationOut]:
    return await get_segmental_duplications_data(
        session,
        assembly=assembly,
        chrom=chrom,
        start=start,
        end=end,
    )

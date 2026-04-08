"""车300估值相关API"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from db.session import get_db_session
from models.valuation import ValuationRequest, ValuationResult
from services.che300_client import get_valuation, batch_valuation

router = APIRouter(prefix="/api/valuation", tags=["估值"])


@router.post("/single", response_model=ValuationResult)
async def single_valuation(
    req: ValuationRequest,
    session: Session = Depends(get_db_session),
):
    """单车估值"""
    try:
        result = await get_valuation(
            session,
            model_id=req.model_id,
            registration_date=req.registration_date,
            mileage=req.mileage,
            city_code=req.city_code,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"估值失败: {str(e)}")


@router.post("/batch")
async def batch_valuation_api(
    items: list[dict],
    session: Session = Depends(get_db_session),
):
    """批量估值"""
    try:
        results = await batch_valuation(session, items)
        return {"results": {str(k): v.model_dump() for k, v in results.items()}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量估值失败: {str(e)}")

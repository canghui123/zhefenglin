"""车300估值相关API"""

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import BusinessError
from db.models.user import User
from models.valuation import ValuationRequest, ValuationResult
from services.che300_client import get_valuation, batch_valuation
from services.tenant_context import get_current_tenant_id

router = APIRouter(
    prefix="/api/valuation",
    tags=["估值"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/single",
    response_model=ValuationResult,
    dependencies=[Depends(require_role("operator"))],
)
async def single_valuation(
    req: ValuationRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """单车估值"""
    try:
        result = await get_valuation(
            session,
            model_id=req.model_id,
            registration_date=req.registration_date,
            mileage=req.mileage,
            city_code=req.city_code,
            tenant_id=tenant_id,
            user_id=user.id,
            module="car-valuation",
            request_id=getattr(request.state, "request_id", None),
            valuation_level="condition_pricing" if req.advanced_condition_pricing else "basic",
            manual_selected=req.manual_selected,
            approval_mode=req.approval_mode,
            single_task_budget=req.single_task_budget,
            strict_policy=req.strict_policy,
        )
        return result
    except BusinessError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"估值失败: {str(e)}")


@router.post("/batch", dependencies=[Depends(require_role("operator"))])
async def batch_valuation_api(
    items: list[dict],
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """批量估值"""
    try:
        results = await batch_valuation(
            session,
            items,
            tenant_id=tenant_id,
            user_id=user.id,
            module="car-valuation",
            request_id=getattr(request.state, "request_id", None),
        )
        return {"results": {str(k): v.model_dump() for k, v in results.items()}}
    except BusinessError:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量估值失败: {str(e)}")

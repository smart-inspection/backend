from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
@router.head("")
def health_check():
    return {"status": "ok", "service": "smart-inspection-reporting-api"}
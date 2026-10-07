from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])

@router.api_route("/health", methods=["GET", "HEAD"], tags=["health"])
def health_check():
    return {"status": "healthy"}
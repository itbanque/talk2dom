from fastapi import APIRouter

router = APIRouter()


@router.get("/debug")
async def trigger_error():
    division_by_zero = 1 / 0

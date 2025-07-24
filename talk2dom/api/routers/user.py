from fastapi import APIRouter, Depends, Request, Body, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from talk2dom.db.models import User, APIKey
from talk2dom.db.session import get_db
from talk2dom.api.deps import get_current_user
import secrets


router = APIRouter()


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
    }


@router.post("/api-keys")
def create_api_key(
    name: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key_value = secrets.token_hex(32)
    api_key = APIKey(user_id=current_user.id, key=key_value, name=name)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {"api_key": key_value, "id": api_key.id, "name": api_key.name}


@router.get("/api-keys")
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "created_at": k.created_at,
            "is_active": k.is_active,
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = (
        db.query(APIKey)
        .filter(APIKey.id == key_id, APIKey.user_id == current_user.id)
        .first()
    )
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(key)
    db.commit()
    return {"detail": "API key deleted"}


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

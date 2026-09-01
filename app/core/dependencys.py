from fastapi import Depends, HTTPException, status

from app.core.security import get_current_token_payload


def require_auth(payload: dict = Depends(get_current_token_payload)):
    return payload


def require_admin(payload: dict = Depends(get_current_token_payload)):
    if payload.get("permission") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin rights required",
        )
    return payload

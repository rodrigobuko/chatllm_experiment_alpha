from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Session as SessionModel, User
from backend.routers.auth import get_current_user
from backend.schemas.session import SessionCreate, SessionOut, SessionRename


router = APIRouter()


@router.get("/api/sessions", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionModel]:
    return (
        db.query(SessionModel)
        .filter(SessionModel.user_id == current_user.id)
        .order_by(SessionModel.updated_at.desc())
        .all()
    )


@router.post("/api/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionModel:
    session = SessionModel(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.patch("/api/sessions/{session_id}", response_model=SessionOut)
def rename_session(
    session_id: int,
    payload: SessionRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionModel:
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_id, SessionModel.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessao nao encontrada.")
    session.title = payload.title
    db.commit()
    db.refresh(session)
    return session


@router.delete("/api/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_id, SessionModel.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessao nao encontrada.")
    db.delete(session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
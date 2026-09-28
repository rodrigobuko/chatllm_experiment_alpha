from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.config import OPENROUTER_MODEL_DEFAULT
from backend.database import get_db
from backend.models import ChatMessage, Session as SessionModel, User
from backend.routers.auth import get_current_user
from backend.schemas.chat import ChatMessageIn, ChatRequest, ChatResponse
from backend.services.openrouter import OpenRouterConfigError, generate_reply, stream_reply


router = APIRouter()


def _auto_title(user_message: str) -> str:
    """Gera um titulo automatico a partir da primeira mensagem do usuario."""
    max_len = 60
    title = user_message.strip().replace("\n", " ")[:max_len]
    if len(user_message) > max_len:
        title += "..."
    return title or "Nova conversa"


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/chat/history/{session_id}", response_model=list[ChatMessageIn])
def chat_history(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessage]:
    # Verifica se a sessao pertence ao usuario
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_key == str(session_id))
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    try:
        reply, model_name = await generate_reply(
            user_message=payload.message,
            history=[item.model_dump() for item in payload.history],
            model=payload.model,
        )
    except OpenRouterConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    resolved_model = payload.model or model_name or OPENROUTER_MODEL_DEFAULT
    session_key = payload.session_id or "default"

    # Se a sessao existe e nao tem titulo personalizado, gera um
    if payload.session_id:
        session = db.query(SessionModel).filter(
            SessionModel.id == payload.session_id,
            SessionModel.user_id == current_user.id,
        ).first()
        if session and session.title == "Nova conversa":
            session.title = _auto_title(payload.message)
            db.commit()

    db.add(ChatMessage(session_key=session_key, role="user", content=payload.message, model=resolved_model))
    db.add(ChatMessage(session_key=session_key, role="assistant", content=reply, model=resolved_model))
    db.commit()

    return ChatResponse(reply=reply, model=resolved_model)


@router.post("/api/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    resolved_model = payload.model or OPENROUTER_MODEL_DEFAULT
    session_key = payload.session_id or "default"

    async def event_generator():
        full_reply = ""
        try:
            async for delta in stream_reply(
                user_message=payload.message,
                history=[item.model_dump() for item in payload.history],
                model=payload.model,
            ):
                full_reply += delta
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=True)}\n\n"
        except OpenRouterConfigError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return
        except RuntimeError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return

        if full_reply.strip():
            # Gera titulo automatico na primeira mensagem
            if payload.session_id:
                session = db.query(SessionModel).filter(
                    SessionModel.id == payload.session_id,
                    SessionModel.user_id == current_user.id,
                ).first()
                if session and session.title == "Nova conversa":
                    session.title = _auto_title(payload.message)
                    db.commit()

            db.add(
                ChatMessage(
                    session_key=session_key,
                    role="user",
                    content=payload.message,
                    model=resolved_model,
                )
            )
            db.add(
                ChatMessage(
                    session_key=session_key,
                    role="assistant",
                    content=full_reply,
                    model=resolved_model,
                )
            )
            db.commit()

        yield f"data: {json.dumps({'done': True}, ensure_ascii=True)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

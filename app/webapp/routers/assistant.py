"""Claude-style chat app: a sidebar of conversations and a streaming thread."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.base import session_scope
from app.db.models import ChatRole, User
from app.observability.logging import get_logger
from app.services import assistant
from app.settings import get_settings
from app.webapp.deps import get_db, require_user
from app.webapp.templating import templates

router = APIRouter()
log = get_logger(__name__)


class ChatTurn(BaseModel):
    message: str


def _convo_dict(c) -> dict:
    return {
        "id": c.id,
        "title": c.title or "New chat",
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _render_shell(request: Request, user: User, db: Session, convo):
    conversations = repo.list_conversations(db, user.id)
    messages = repo.list_messages(db, convo.id) if convo else []
    return templates.TemplateResponse(
        request,
        "assistant.html",
        {
            "user": user,
            "conversations": conversations,
            "conversation": convo,
            "messages": messages,
        },
    )


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    # Open a blank new chat; existing threads are in the sidebar.
    return _render_shell(request, user, db, convo=None)


@router.get("/c/{conversation_id}", response_class=HTMLResponse)
async def conversation_page(
    request: Request,
    conversation_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    convo = repo.get_conversation(db, conversation_id, user.id)
    if convo is None:
        return _render_shell(request, user, db, convo=None)
    return _render_shell(request, user, db, convo)


@router.get("/api/conversations")
async def list_conversations(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    convos = repo.list_conversations(db, user.id)
    return {"conversations": [_convo_dict(c) for c in convos]}


@router.post("/api/conversations")
async def new_conversation(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    convo = repo.create_conversation(db, user.id, job_id=None, title="")
    db.commit()
    return {"id": convo.id}


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    ok = repo.delete_conversation(db, conversation_id, user.id)
    db.commit()
    if not ok:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"deleted": True}


@router.post("/api/conversations/{conversation_id}/message")
async def send_message(
    conversation_id: str,
    turn: ChatTurn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    s = get_settings()
    question = (turn.message or "").strip()
    if not question:
        return JSONResponse({"error": "Message is required."}, status_code=422)
    if len(question) > s.chat_max_message_len:
        return JSONResponse(
            {"error": f"Message exceeds {s.chat_max_message_len} characters."},
            status_code=422,
        )

    convo = repo.get_conversation(db, conversation_id, user.id)
    if convo is None:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    if not convo.title:
        repo.set_conversation_title(db, convo.id, assistant.make_title(question))
    repo.add_message(db, convo.id, ChatRole.USER.value, question)
    db.commit()

    history = [(m.role, m.content) for m in repo.list_messages(db, convo.id)]
    cid = convo.id

    def generate():
        chunks: list[str] = []
        try:
            for piece in assistant.stream_reply(history):
                chunks.append(piece)
                yield piece
        except Exception as exc:  # noqa: BLE001 - surface a clean message
            log.error("assistant.stream_failed", conversation_id=cid, error=str(exc))
            note = "\n\n_(The assistant could not finish responding.)_"
            chunks.append(note)
            yield note
        finally:
            full = "".join(chunks).strip()
            if full:
                with session_scope() as s2:
                    repo.add_message(s2, cid, ChatRole.ASSISTANT.value, full)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

"""Chat grounded on a report: a page per conversation and a JSON turn endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.models import ChatRole, User
from app.observability.logging import get_logger
from app.services import chat as chat_service
from app.settings import get_settings
from app.webapp.deps import get_db, require_user
from app.webapp.templating import templates

router = APIRouter()
log = get_logger(__name__)


class ChatTurn(BaseModel):
    message: str


@router.get("/chat/{job_id}", response_class=HTMLResponse)
async def chat_page(
    request: Request,
    job_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = repo.get_job(db, job_id, user.tenant_id)
    if job is None or job.report is None:
        # Can only chat once a report exists to ground the conversation.
        return RedirectResponse(f"/research/{job_id}", status_code=303)

    convo = repo.get_conversation_for_job(db, job.id, user.id)
    if convo is None:
        convo = repo.create_conversation(db, user.id, job.id, title=job.topic)
        db.commit()

    messages = repo.list_messages(db, convo.id)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "user": user,
            "job": job,
            "conversation_id": convo.id,
            "messages": messages,
        },
    )


@router.post("/api/chat/{conversation_id}")
async def chat_turn(
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

    job = repo.get_job(db, convo.job_id, user.tenant_id)
    if job is None or job.report is None:
        return JSONResponse(
            {"error": "The report for this conversation is unavailable."},
            status_code=409,
        )

    history = [(m.role, m.content) for m in repo.list_messages(db, convo.id)]
    repo.add_message(db, convo.id, ChatRole.USER.value, question)
    db.commit()  # persist the question before the (possibly slow) LLM call

    try:
        answer = chat_service.answer(
            topic=job.topic,
            report_markdown=job.report.markdown,
            history=history,
            question=question,
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the UI
        log.error("chat.failed", conversation_id=convo.id, error=str(exc))
        db.rollback()
        return JSONResponse(
            {"error": "The assistant could not answer right now."},
            status_code=502,
        )

    repo.add_message(db, convo.id, ChatRole.ASSISTANT.value, answer)
    db.commit()
    log.info("chat.turn", conversation_id=convo.id, user_id=user.id)
    return {"answer": answer}

"""Theater routes."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from config import (
    HEALTH_STATUS_OK,
    THEATER_ROUTER_PREFIX,
    THEATER_ROUTER_TAG,
)
from services.review_service import ReviewReportData, generate_review_report
from services.template_service import TheaterTemplateData, list_templates
from services.theater_service import ChatData, process_chat_message

router = APIRouter(prefix=THEATER_ROUTER_PREFIX, tags=[THEATER_ROUTER_TAG])


class HealthResponse(BaseModel):
    status: str
    service: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[dict] = Field(default_factory=list)
    scam_id: str


class ChatResponse(BaseModel):
    scammer_reply: str | None
    risk_level: str
    risk_score: int
    risk_message: str
    interrupted: bool


class TheaterTemplateResponse(BaseModel):
    scam_id: str
    scam_name: str
    target: str
    difficulty: int
    opener: str
    persona: str
    escalation_steps: list[str]
    red_flags: list[str]
    prevention: list[str]


class TheaterTemplatesResponse(BaseModel):
    templates: list[TheaterTemplateResponse]


class RevealRequest(BaseModel):
    session_id: str
    scam_id: str


class RevealResponse(BaseModel):
    session_id: str
    scam_id: str
    scam_name: str
    summary: str
    conversation_turns: int
    highest_risk_level: str
    highest_risk_score: int
    tactics: list[str]
    red_flags: list[str]
    prevention: list[str]
    legal: str
    typical_case: str
    review_title: str
    review_content: str
    key_takeaways: list[str]


@router.get("/health", response_model=HealthResponse)
async def theater_health() -> HealthResponse:
    return HealthResponse(status=HEALTH_STATUS_OK, service=THEATER_ROUTER_TAG)


@router.get("/templates", response_model=TheaterTemplatesResponse)
async def theater_templates() -> TheaterTemplatesResponse:
    templates: list[TheaterTemplateData] = list_templates()
    return TheaterTemplatesResponse(
        templates=[
            TheaterTemplateResponse(
                scam_id=template.scam_id,
                scam_name=template.scam_name,
                target=template.target,
                difficulty=template.difficulty,
                opener=template.opener,
                persona=template.persona,
                escalation_steps=template.escalation_steps,
                red_flags=template.red_flags,
                prevention=template.prevention,
            )
            for template in templates
        ]
    )


@router.post("/reveal", response_model=RevealResponse)
async def theater_reveal(body: RevealRequest) -> RevealResponse:
    review: ReviewReportData = generate_review_report(
        session_id=body.session_id,
        scam_id=body.scam_id,
    )
    return RevealResponse(
        session_id=review.session_id,
        scam_id=review.scam_id,
        scam_name=review.scam_name,
        summary=review.summary,
        conversation_turns=review.conversation_turns,
        highest_risk_level=review.highest_risk_level,
        highest_risk_score=review.highest_risk_score,
        tactics=review.tactics,
        red_flags=review.red_flags,
        prevention=review.prevention,
        legal=review.legal,
        typical_case=review.typical_case,
        review_title=review.review_title,
        review_content=review.review_content,
        key_takeaways=review.key_takeaways,
    )


@router.post("/chat", response_model=ChatResponse)
async def theater_chat(request: Request, body: ChatRequest) -> ChatResponse:
    chat: ChatData = process_chat_message(
        session_id=body.session_id,
        message=body.message,
        history=body.history,
        scam_id=body.scam_id,
        risk_rules=request.app.state.risk_rules,
    )
    return ChatResponse(
        scammer_reply=chat.scammer_reply,
        risk_level=chat.risk_level,
        risk_score=chat.risk_score,
        risk_message=chat.risk_message,
        interrupted=chat.interrupted,
    )

"""User routes."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from config import HEALTH_STATUS_OK, USER_ROUTER_PREFIX, USER_ROUTER_TAG
from services.gamification import CompleteScenarioData, UserProgressData, complete_scenario, get_progress

router = APIRouter(prefix=USER_ROUTER_PREFIX, tags=[USER_ROUTER_TAG])


class HealthResponse(BaseModel):
    status: str
    service: str


class UserProgressResponse(BaseModel):
    user_id: str
    total_score: int
    streak: int
    badges: list[str]
    completed: dict[str, int]


class CompleteScenarioRequest(BaseModel):
    user_id: str
    scam_id: str
    session_id: str | None = None


class CompleteScenarioResponse(UserProgressResponse):
    score_added: int
    new_badges: list[str]
    status: str
    message: str
    already_claimed: bool


@router.get("/health", response_model=HealthResponse)
async def user_health() -> HealthResponse:
    return HealthResponse(status=HEALTH_STATUS_OK, service=USER_ROUTER_TAG)


@router.get("/progress", response_model=UserProgressResponse)
async def user_progress(user_id: str = Query(...)) -> UserProgressResponse:
    progress: UserProgressData = get_progress(user_id)
    return UserProgressResponse(
        user_id=progress.user_id,
        total_score=progress.total_score,
        streak=progress.streak,
        badges=progress.badges,
        completed=progress.completed,
    )


@router.post("/complete", response_model=CompleteScenarioResponse)
async def user_complete(req: CompleteScenarioRequest) -> CompleteScenarioResponse:
    result: CompleteScenarioData = complete_scenario(
        user_id=req.user_id,
        scam_id=req.scam_id,
        session_id=req.session_id,
    )
    return CompleteScenarioResponse(
        user_id=result.user_id,
        total_score=result.total_score,
        streak=result.streak,
        badges=result.badges,
        completed=result.completed,
        score_added=result.score_added,
        new_badges=result.new_badges,
        status=result.status,
        message=result.message,
        already_claimed=result.already_claimed,
    )

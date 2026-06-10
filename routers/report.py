"""Report routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from config import HEALTH_STATUS_OK, REPORT_ROUTER_PREFIX, REPORT_ROUTER_TAG
from services.report_service import ReportData, submit_report

router = APIRouter(prefix=REPORT_ROUTER_PREFIX, tags=[REPORT_ROUTER_TAG])


class HealthResponse(BaseModel):
    status: str
    service: str


class ReportSubmitRequest(BaseModel):
    session_id: str | None = None
    content: str | None = None
    url: str | None = None
    risk_level: str | None = None


class ReportSubmitResponse(BaseModel):
    report_id: str
    status: str
    message: str


@router.get("/health", response_model=HealthResponse)
async def report_health() -> HealthResponse:
    return HealthResponse(status=HEALTH_STATUS_OK, service=REPORT_ROUTER_TAG)


@router.post("/submit", response_model=ReportSubmitResponse)
async def report_submit(req: ReportSubmitRequest) -> ReportSubmitResponse:
    report: ReportData = submit_report(
        session_id=req.session_id,
        content=req.content,
        url=req.url,
        risk_level=req.risk_level,
    )
    return ReportSubmitResponse(
        report_id=report.report_id,
        status=report.status,
        message=report.message,
    )

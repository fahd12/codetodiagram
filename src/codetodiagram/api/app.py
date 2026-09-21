"""FastAPI application for local diagram generation."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codetodiagram.api.schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse
from codetodiagram.api.service import analyze_request

app = FastAPI(title="codetodiagram", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return a liveness payload."""
    return HealthResponse(status="ok")


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a local path or public GitHub repository."""
    return analyze_request(payload)

"""Request and response models for the local web API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from codetodiagram.models import MetadataValue


class AnalyzeRequest(BaseModel):
    """Analyze a local path or a public GitHub repository."""

    source: str = Field(..., min_length=1, description="Local path or GitHub HTTPS URL")
    ref: str | None = Field(default=None, description="Optional git branch or tag")
    entry: list[str] | None = Field(default=None, description="Entry-point name filters")
    max_depth: int = Field(default=10, ge=0, le=50)
    max_nodes: int = Field(default=50, ge=0, le=500)


class AnalyzeResponse(BaseModel):
    """Mermaid document plus the entries used to build it."""

    mermaid: str
    entries: list[str]
    metadata: dict[str, MetadataValue]


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: str

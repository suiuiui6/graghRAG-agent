"""Pydantic data models — follows backend-api-architecture-v1.0.md §4."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class PipelineStage(str, Enum):
    UPLOAD = "upload"
    MINERU = "mineru"
    BRIDGE = "bridge"
    EXTRACTION = "extraction"
    GROUNDING = "grounding"
    KG_BUILD = "kg_build"
    COMPLETED = "completed"


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".png", ".jpg", ".jpeg", ".epub", ".html"}
MAX_FILE_SIZE = 200 * 1024 * 1024


# ---- Request Models ----
class QueryOptions(BaseModel):
    max_tool_calls: int = Field(default=10, ge=1, le=50)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    language: str = Field(default="en", pattern="^(en|ch|ja)$")
    include_sources: bool = Field(default=True)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    document_id: Optional[str] = None
    options: QueryOptions = Field(default_factory=QueryOptions)


# ---- Response Models ----
class SourceNode(BaseModel):
    node_id: str
    entity_type: str
    label: str
    properties: dict
    page_idx: Optional[int]
    bbox_norm: Optional[list[float]]
    grounding_status: str
    relevance_score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: Optional[list[SourceNode]] = None
    subgraph: Optional[dict] = None
    metadata: dict


class StageProgress(BaseModel):
    stage_name: str
    current_step: int
    total_steps: int = 5
    details: dict


class TaskResult(BaseModel):
    document_id: Optional[str] = None
    kg_nodes: Optional[int] = None
    kg_edges: Optional[int] = None
    grounded_entities: Optional[int] = None
    entity_types: Optional[int] = None
    pages_parsed: Optional[int] = None
    kg_path: Optional[str] = None


class TaskError(BaseModel):
    code: str
    message: str


class IngestResponse(BaseModel):
    task_id: str
    status: TaskStatus
    filename: str
    file_size_bytes: int
    created_at: datetime
    estimated_duration_seconds: int
    links: dict


class StatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    stage: Optional[PipelineStage] = None
    progress: Optional[StageProgress] = None
    result: Optional[TaskResult] = None
    error: Optional[TaskError] = None
    created_at: datetime
    updated_at: datetime
    duration_seconds: Optional[int] = None


class DocumentItem(BaseModel):
    document_id: str
    filename: str
    status: str
    kg_nodes: Optional[int] = None
    kg_edges: Optional[int] = None
    pages: Optional[int] = None
    indexed_at: Optional[datetime] = None
    file_size_mb: Optional[float] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    total: int


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: int
    components: dict
    stats: dict


class DeleteResponse(BaseModel):
    document_id: str
    status: str
    deleted_at: datetime


class ErrorResponse(BaseModel):
    error: TaskError

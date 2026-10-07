"""Pydantic data models — follows backend-api-architecture-v1.0.md §4."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal
from datetime import datetime
from enum import Enum
from source_control import normalize_enabled_sources

from config import (
    DEFAULT_ENABLE_CROSS_ENCODER,
    DEFAULT_ENABLE_GLOBAL_MODE,
    DEFAULT_ENABLE_MULTI_QUERY,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MAX_TOTAL_CANDIDATES,
    default_per_source_caps,
)


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
    max_total_candidates: int = Field(default=DEFAULT_MAX_TOTAL_CANDIDATES, ge=1, le=50)
    max_context_tokens: int = Field(default=DEFAULT_MAX_CONTEXT_TOKENS, ge=512, le=16000)
    enable_cross_encoder: bool = Field(default=DEFAULT_ENABLE_CROSS_ENCODER)
    enable_multi_query: bool = Field(default=DEFAULT_ENABLE_MULTI_QUERY)
    enable_global_mode: bool = Field(default=DEFAULT_ENABLE_GLOBAL_MODE)
    per_source_caps: dict[str, int] = Field(default_factory=default_per_source_caps)
    enabled_sources: list[Literal["vector", "kg", "bm25", "table", "multi_query"]] | None = None

    @field_validator("enabled_sources", mode="before")
    @classmethod
    def validate_enabled_sources(cls, value):
        normalized = normalize_enabled_sources(value)
        return None if normalized is None else list(normalized)

    @field_validator("per_source_caps")
    @classmethod
    def validate_per_source_caps(cls, value: dict[str, int]) -> dict[str, int]:
        allowed_sources = set(default_per_source_caps().keys())
        invalid_sources = sorted(set(value.keys()) - allowed_sources)
        if invalid_sources:
            raise ValueError(
                f"Unsupported per_source_caps keys: {', '.join(invalid_sources)}"
            )

        for source_name, cap in value.items():
            if not 1 <= cap <= 50:
                raise ValueError(
                    f"per_source_caps[{source_name}] must be between 1 and 50"
                )

        return value


class QueryRequest(BaseModel):
    query: str = Field(default="", min_length=0, max_length=2000)
    question: str | None = None
    document_id: str | None = None
    session_id: str | None = None  # §10.2: multi-turn conversation
    options: QueryOptions = Field(default_factory=QueryOptions)

    @model_validator(mode="after")
    def normalize_query(self):
        if not self.query and self.question:
            self.query = self.question
        if not self.query:
            raise ValueError("query or question is required")
        return self


# ---- Response Models ----
class SourceNode(BaseModel):
    node_id: str
    entity_type: str
    label: str
    properties: dict
    page_idx: int | None
    bbox_norm: list[float] | None
    grounding_status: str
    relevance_score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[SourceNode] | None = None
    subgraph: dict | None = None
    metadata: dict


class StageProgress(BaseModel):
    stage_name: str
    current_step: int
    total_steps: int = 5
    details: dict


class TaskResult(BaseModel):
    document_id: str | None = None
    kg_nodes: int | None = None
    kg_edges: int | None = None
    grounded_entities: int | None = None
    entity_types: int | None = None
    pages_parsed: int | None = None
    kg_path: str | None = None
    partial: bool = False          # 部分批次失败：任务完成但结果不完整
    warnings: list[str] = []       # 降级/空结果的用户可见提示


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
    stage: PipelineStage | None = None
    progress: StageProgress | None = None
    result: TaskResult | None = None
    error: TaskError | None = None
    created_at: datetime
    updated_at: datetime
    duration_seconds: int | None = None


class DocumentItem(BaseModel):
    document_id: str
    filename: str
    status: str
    kg_nodes: int | None = None
    kg_edges: int | None = None
    pages: int | None = None
    indexed_at: datetime | None = None
    file_size_mb: float | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    total: int


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: int
    components: dict = {}
    stats: dict = {}
    dependencies: dict = {}


class DeleteResponse(BaseModel):
    document_id: str
    status: str
    deleted_at: datetime


class ErrorResponse(BaseModel):
    error: TaskError


# ---- Feedback Models (§4.1) ----

class FeedbackCreate(BaseModel):
    query_id: str | None = None
    rating: Literal["positive", "negative"]
    comment: str | None = None
    correction: str | None = None
    chunks_cited: list[str] | None = None
    user_id: str | int | None = None


class FeedbackRecord(FeedbackCreate):
    feedback_id: str
    created_at: str
    query_text: str = ""
    answer_text: str = ""
    status: str = "open"  # open | acknowledged | resolved


class FeedbackUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"] | None = None
    comment: str | None = None


class FeedbackStats(BaseModel):
    total: int
    positive: int
    negative: int
    positive_ratio: float
    by_status: dict
    recent_negative: list[FeedbackRecord]


# ---- Phase 2: Lineage Models (§5.1) ----

class LineageNodeType(str, Enum):
    DOCUMENT = "document"
    SECTION = "section"
    EXTRACTION = "extraction"
    ENTITY = "entity"
    CHUNK = "chunk"
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    ANSWER = "answer"
    FEEDBACK = "feedback"
    DOMAIN_EXPAND = "domain_expand"
    CONVERSATION_TURN = "conv_turn"
    KG_VERSION = "kg_version"


class LineageNode(BaseModel):
    node_id: str
    node_type: LineageNodeType
    label: str
    metadata: dict = {}
    parent_ids: list[str] = []
    child_ids: list[str] = []
    session_id: str | None = None
    kg_version: int | None = None
    domain_terms: list[str] | None = None
    feedback_id: str | None = None
    timestamp: str | None = None


class LineageTrace(BaseModel):
    entity_id: str
    trace: list[LineageNode]
    direction: str = "forward"  # forward | backward


# ---- Phase 2: Catalog Models (§5.2) ----

class CatalogSummary(BaseModel):
    summary: dict
    domain_dict: dict | None = None
    conversations: dict | None = None
    feedback: dict | None = None
    retrieval: dict | None = None
    quality_metrics: dict | None = None
    last_updated: str


class CatalogTrends(BaseModel):
    days: int
    entity_growth: list[dict]
    query_volume: list[dict]
    feedback_rate: list[dict]


# ---- Phase 2: Export Models (§5.3) ----

class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    RDF = "rdf"
    NEO4J = "neo4j"
    ZIP = "zip"
    YAML = "yaml"


# ---- Phase 2: Backup Models (§5.4) ----

class BackupManifest(BaseModel):
    backup_id: str
    created_at: str
    backup_type: str  # daily | weekly | manual
    directories: list[str]
    total_files: int
    total_size_bytes: int
    kg_nodes: int | None = None
    kg_edges: int | None = None
    checksum: str | None = None


class BackupResult(BaseModel):
    backup_id: str
    status: str
    manifest: BackupManifest | None = None
    error: str | None = None


class RestoreResult(BaseModel):
    status: str
    restored_from: str
    pre_restore_snapshot: str | None = None


# ---- Phase 2: Quality Models (§5.5) ----

class QualityReport(BaseModel):
    extraction_quality: dict
    retrieval_quality: dict
    feedback_quality: dict
    data_freshness: dict
    overall_score: float
    alerts: list[dict]
    generated_at: str


# ---- Phase 2: Lifecycle Models (§5.6) ----

class CleanupPreview(BaseModel):
    category: str
    policy: dict
    items_to_remove: int
    items_sample: list[str]


class CleanupReport(BaseModel):
    executed_at: str
    categories: dict
    total_removed: int
    errors: list[str]


class StorageReport(BaseModel):
    directories: dict
    total_size_bytes: int
    last_checked: str


# ---- Phase 3: SSO/Auth Models (§6.1) ----

class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(BaseModel):
    user_id: str
    username: str
    email: str
    display_name: str
    roles: list[str] = ["viewer"]
    department: str | None = None
    avatar_url: str | None = None
    created_at: str
    last_login: str | None = None
    auth_provider: str = "local"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600


class OAuth2Config(BaseModel):
    provider: str
    issuer_url: str
    client_id: str
    redirect_uri: str
    scopes: list[str] = ["openid", "profile", "email"]


class LoginRequest(BaseModel):
    username: str | None = None
    password: str | None = None
    provider: str = "local"


# ---- Phase 3: Bot Models (§6.2) ----

class BotConfig(BaseModel):
    platform: str
    app_id: str
    verification_token: str | None = None
    encrypt_key: str | None = None
    webhook_url: str | None = None
    enabled: bool = True
    daily_limit: int = 500


class BotMessage(BaseModel):
    platform: str
    event_type: str
    sender_id: str
    sender_name: str
    chat_id: str
    text: str
    raw: dict
    timestamp: str


# ---- Phase 3: Webhook Models (§6.3) ----

class WebhookCreate(BaseModel):
    url: str
    events: list[str]
    secret: str | None = None
    description: str = ""


class WebhookRecord(WebhookCreate):
    webhook_id: str
    created_at: str
    enabled: bool = True
    last_delivery_at: str | None = None
    delivery_count: int = 0
    failed_count: int = 0


class WebhookEvent(BaseModel):
    event_id: str
    event_type: str
    timestamp: str
    source: str = "graphrag-backend"
    version: str = "1.0"
    data: dict


class DeliveryLog(BaseModel):
    delivery_id: str
    webhook_id: str
    event_id: str
    status: str  # pending | success | failed
    attempt: int
    status_code: int | None = None
    error: str | None = None
    timestamp: str


# ---- Phase 3: Audit Models (§6.5) ----

class AuditRecord(BaseModel):
    event: str
    user_id: str
    timestamp: str
    ip: str = ""
    user_agent: str = ""
    details: dict = {}


# ---- Phase 3: API Key Models (§6.6) ----

class ApiKeyScope(str, Enum):
    READ_QUERY = "read:query"
    READ_CATALOG = "read:catalog"
    READ_EXPORT = "read:export"
    WRITE_INGEST = "write:ingest"
    WRITE_FEEDBACK = "write:feedback"
    WRITE_DICT = "write:dict"
    ADMIN_SYSTEM = "admin:system"
    ADMIN_KEYS = "admin:keys"


class ApiKeyCreate(BaseModel):
    name: str
    expires_at: str | None = None
    scopes: list[str] = ["read:query"]
    rate_limit_per_minute: int = 60


class ApiKeyRecord(BaseModel):
    key_id: str
    name: str
    key_prefix: str
    key_hash: str
    created_by: str
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None
    revoked: bool = False
    scopes: list[str] = ["read:query"]
    rate_limit_per_minute: int = 60


class ApiKeyResponse(BaseModel):
    key_id: str
    name: str
    key_prefix: str
    full_key: str
    created_at: str
    expires_at: str | None = None
    scopes: list[str]


# ---- Phase 3: Health Models (§6.7) ----

class DependencyStatus(BaseModel):
    status: str  # ok | degraded | down
    latency_ms: int | None = None
    message: str | None = None


# ---- Phase 4: Multi-tenancy Models (§7.1) ----


class Organization(BaseModel):
    org_id: str
    name: str
    slug: str
    contact_email: str | None = None
    plan: str = "free"
    max_projects: int = 5
    max_users: int = 20
    max_storage_mb: int = 500
    created_at: str
    updated_at: str | None = None
    is_active: bool = True


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    contact_email: str | None = None


class Project(BaseModel):
    project_id: str
    org_id: str
    name: str
    description: str = ""
    project_code: str | None = None
    created_by: str
    created_at: str
    updated_at: str | None = None
    is_archived: bool = False


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    project_code: str | None = None


class OrgMembership(BaseModel):
    membership_id: str
    org_id: str
    user_id: str
    username: str = ""
    role: str  # org_admin | org_editor | org_viewer
    joined_at: str
    invited_by: str | None = None


class MemberInvite(BaseModel):
    user_id: str
    role: str = "org_viewer"


class RoleUpdate(BaseModel):
    role: str  # org_admin | org_editor | org_viewer

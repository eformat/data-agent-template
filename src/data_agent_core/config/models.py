"""Pydantic v2 configuration models for domain agents."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ColumnInfo(BaseModel):
    """Schema for a single table column."""

    name: str
    type: str
    description: str = ""


class DatasetInfo(BaseModel):
    """Metadata for a single dataset/table."""

    name: str
    formal_name: str = ""
    description: str = ""
    category: str = ""
    years_available: str = ""
    columns: list[ColumnInfo] = []
    aliases: dict[str, str] = {}
    key_features: list[str] = []
    limitations: list[str] = []


class MethodologyInfo(BaseModel):
    """Collection methodology for a dataset."""

    collection_design: str
    case_definition: str = ""
    instruments: str = ""
    population_coverage: str = ""
    known_biases: list[str] = []
    geographic_resolution: str = "State/territory"
    temporal_resolution: str = ""
    update_frequency: str = ""


class EnrichmentConfig(BaseModel):
    """MCP enrichment contract — what the agent can and cannot conclude."""

    geographic_resolution: str = ""
    unsupported_conclusions: list[str] = []
    supported_conclusions: list[str] = []
    caveats: list[str] = []


class ComputedStatistic(BaseModel):
    """A domain-specific computed statistic."""

    name: str
    formula: str
    description: str = ""


class StarterQuestion(BaseModel):
    """Chainlit starter question."""

    label: str
    message: str


class SeedQuestion(BaseModel):
    """Evaluation seed question."""

    question: str
    expected_tools: list[str] = []
    expected_keywords: list[str] = []
    question_type: str = "data_retrieval"
    can_server_answer: str = "yes"
    forbidden_content: list[str] = []


class ResourceSpec(BaseModel):
    """CPU/memory resource requests and limits."""

    cpu_request: str = "200m"
    memory_request: str = "512Mi"
    cpu_limit: str = "1"
    memory_limit: str = "1Gi"


class DeploymentConfig(BaseModel):
    """OpenShift/K8s deployment configuration."""

    namespace: str = ""
    registry: str = ""
    agent_image: str = ""
    mcp_image: str = ""
    replicas: int = 1

    model_name: str = ""
    model_endpoint: str = ""

    trino_host: str = "trino.trino.svc.cluster.local"
    trino_port: int = 8443

    mlflow_tracking_uri: str = ""
    mlflow_workspace: str = ""

    s3_endpoint: str = ""
    s3_bucket: str = ""

    agent_resources: ResourceSpec = ResourceSpec()
    mcp_resources: ResourceSpec = ResourceSpec(
        cpu_request="100m", cpu_limit="500m",
    )

    chainlit_pvc_size: str = "2Gi"
    route_timeout: str = "600s"
    route_tls_termination: str = "edge"


class DomainConfig(BaseModel):
    """Central configuration for a domain agent.

    Domain projects define one instance; all factory functions consume it.
    """

    model_config = ConfigDict(validate_assignment=True)

    # Identity
    domain_name: str
    domain_display_name: str
    domain_description: str

    # Data access
    trino_catalog: str = "lakehouse"
    trino_schema: str = ""

    # Domain data
    datasets: dict[str, DatasetInfo] = {}
    methodology: dict[str, MethodologyInfo] = {}
    aliases: dict[str, str] = {}
    formal_names: dict[str, str] = {}
    enrichment: EnrichmentConfig = EnrichmentConfig()
    computed_statistics: list[ComputedStatistic] = []

    # MCP enrichment contract
    query_tool_docstring: str = ""
    query_result_methodology: str = ""
    dataset_source_name: str = ""
    dataset_source_url: str = ""
    citation_source: str = ""
    citation_url: str = ""

    # System prompt
    system_prompt: str = ""

    # MLflow
    mlflow_experiment_name: str = ""
    mlflow_prompt_name: str = ""
    mlflow_span_name: str = ""

    # Agent UI
    starters: list[StarterQuestion] = []
    step_description: str = "Querying data..."
    fallback_reasoning_template: str = ""

    # Evaluation
    seed_questions: list[SeedQuestion] = []

    # Deployment
    deployment: DeploymentConfig = DeploymentConfig()

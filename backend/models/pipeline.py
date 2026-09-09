from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IngestionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunking_strategy: str
    chunk_size_tokens: int = Field(gt=0)
    chunk_overlap_tokens: int = Field(ge=0)
    extractors_enabled: list[str]


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dense_k: int = Field(gt=0)
    sparse_k: int = Field(gt=0)
    reranker: str
    top_k_after_rerank: int = Field(gt=0)
    query_expansion: bool
    metadata_filters_enabled: bool


class ModelRoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str
    max_cost_per_call: float = Field(ge=0)


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_routing: ModelRoutingConfig
    max_context_tokens: int = Field(gt=0)
    temperature: float = Field(ge=0, le=2)
    system_prompt_variant: str


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_evaluate: bool
    training_threshold: float = Field(ge=0, le=1)


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    ingestion: IngestionConfig
    retrieval: RetrievalConfig
    generation: GenerationConfig
    evaluation: EvaluationConfig

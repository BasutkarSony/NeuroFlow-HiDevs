from pydantic import BaseModel, ConfigDict, Field


class IngestionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunking_strategy: str = Field(description="Chunking strategy used during document ingestion.", examples=["recursive"])
    chunk_size_tokens: int = Field(gt=0, description="Maximum target chunk size in tokens.", examples=[512])
    chunk_overlap_tokens: int = Field(ge=0, description="Number of overlapping tokens between adjacent chunks.", examples=[64])
    extractors_enabled: list[str] = Field(description="Document extractors enabled for ingestion.", examples=[["pdf", "text"]])


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dense_k: int = Field(gt=0, description="Number of dense-vector candidates to retrieve.", examples=[20])
    sparse_k: int = Field(gt=0, description="Number of sparse-search candidates to retrieve.", examples=[20])
    reranker: str = Field(description="Reranking strategy or model.", examples=["cross-encoder"])
    top_k_after_rerank: int = Field(gt=0, description="Number of candidates retained after reranking.", examples=[5])
    query_expansion: bool = Field(description="Whether query expansion is enabled.", examples=[True])
    metadata_filters_enabled: bool = Field(description="Whether metadata filtering is enabled.", examples=[True])
    candidate_k: int = Field(default=40, gt=0, description="Candidate pool size before fusion.", examples=[40])
    reranker_candidate_k: int = Field(default=40, gt=0, description="Number of fused candidates sent to the reranker.", examples=[40])
    fusion_k: int = Field(default=60, gt=0, description="Candidate depth used during reciprocal-rank fusion.", examples=[60])
    dense_weight: float = Field(default=1.0, ge=0, description="Weight applied to dense retrieval scores.", examples=[1.0])
    sparse_weight: float = Field(default=1.0, ge=0, description="Weight applied to sparse retrieval scores.", examples=[1.0])
    metadata_weight: float = Field(default=1.0, ge=0, description="Weight applied to metadata retrieval scores.", examples=[1.0])
    metadata_k: int = Field(default=20, gt=0, description="Number of metadata candidates considered during fusion.", examples=[20])


class ModelRoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str = Field(description="Task type used to select the model provider.", examples=["generation"])
    max_cost_per_call: float = Field(ge=0, description="Maximum permitted cost for one model call.", examples=[0.05])


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_routing: ModelRoutingConfig = Field(description="Model routing configuration.")
    max_context_tokens: int = Field(gt=0, description="Maximum context size supplied to the model.", examples=[4096])
    temperature: float = Field(ge=0, le=2, description="Sampling temperature.", examples=[0.2])
    system_prompt_variant: str = Field(description="System prompt variant used for generation.", examples=["default"])


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_evaluate: bool = Field(description="Whether completed runs are automatically evaluated.", examples=[True])
    training_threshold: float = Field(ge=0, le=1, description="Minimum evaluation score required for training eligibility.", examples=[0.8])


class PipelineConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{
            "name": "support-rag",
            "description": "Support knowledge retrieval pipeline",
            "ingestion": {
                "chunking_strategy": "recursive",
                "chunk_size_tokens": 512,
                "chunk_overlap_tokens": 64,
                "extractors_enabled": ["pdf", "text"]
            },
            "retrieval": {
                "dense_k": 20,
                "sparse_k": 20,
                "reranker": "cross-encoder",
                "top_k_after_rerank": 5,
                "query_expansion": True,
                "metadata_filters_enabled": True,
                "candidate_k": 40,
                "reranker_candidate_k": 40,
                "fusion_k": 60,
                "dense_weight": 1.0,
                "sparse_weight": 1.0,
                "metadata_weight": 1.0,
                "metadata_k": 20
            },
            "generation": {
                "model_routing": {
                    "task_type": "generation",
                    "max_cost_per_call": 0.05
                },
                "max_context_tokens": 4096,
                "temperature": 0.2,
                "system_prompt_variant": "default"
            },
            "evaluation": {
                "auto_evaluate": True,
                "training_threshold": 0.8
            }
        }]}
    )

    name: str = Field(description="Unique pipeline name.", examples=["support-rag"])
    description: str = Field(default="", description="Human-readable pipeline description.", examples=["Support knowledge retrieval pipeline"])
    ingestion: IngestionConfig = Field(description="Document ingestion configuration.")
    retrieval: RetrievalConfig = Field(description="Retrieval and ranking configuration.")
    generation: GenerationConfig = Field(description="LLM generation and routing configuration.")
    evaluation: EvaluationConfig = Field(description="Evaluation and training configuration.")

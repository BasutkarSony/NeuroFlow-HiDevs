import pytest
from pydantic import ValidationError

from backend.models.pipeline import (
    EvaluationConfig,
    GenerationConfig,
    IngestionConfig,
    ModelRoutingConfig,
    PipelineConfig,
    RetrievalConfig,
)


def valid_config():
    return {
        "name": "test",
        "ingestion": {
            "chunking_strategy": "fixed",
            "chunk_size_tokens": 500,
            "chunk_overlap_tokens": 50,
            "extractors_enabled": ["pdf"],
        },
        "retrieval": {
            "dense_k": 10,
            "sparse_k": 10,
            "reranker": "default",
            "top_k_after_rerank": 5,
            "query_expansion": False,
            "metadata_filters_enabled": True,
        },
        "generation": {
            "model_routing": {
                "task_type": "qa",
                "max_cost_per_call": 1.0,
            },
            "max_context_tokens": 4000,
            "temperature": 0.2,
            "system_prompt_variant": "default",
        },
        "evaluation": {
            "auto_evaluate": True,
            "training_threshold": 0.8,
        },
    }


def test_valid_config():
    assert PipelineConfig.model_validate(valid_config()).name == "test"


def test_rejects_zero_chunk_size():
    data = valid_config()
    data["ingestion"]["chunk_size_tokens"] = 0
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate(data)


def test_rejects_negative_cost():
    data = valid_config()
    data["generation"]["model_routing"]["max_cost_per_call"] = -1
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate(data)


def test_rejects_invalid_temperature():
    data = valid_config()
    data["generation"]["temperature"] = 3
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate(data)


def test_rejects_extra_fields():
    data = valid_config()
    data["unexpected"] = True
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate(data)

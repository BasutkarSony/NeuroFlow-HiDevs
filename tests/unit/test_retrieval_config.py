import pytest

from pipelines.retrieval.fusion import (
    RetrievalResult,
    reciprocal_rank_fusion,
)


def result(chunk_id):
    return RetrievalResult(
        chunk_id=chunk_id,
        content=chunk_id,
        score=1.0,
        metadata={},
    )


def get_score(results, chunk_id):
    return next(r.score for r in results if r.chunk_id == chunk_id)


def test_weighted_rrf_changes_score():
    dense = [result("shared")]
    sparse = [result("shared")]

    equal = reciprocal_rank_fusion(
        [dense, sparse],
        weights=[1.0, 1.0],
    )

    dense_weighted = reciprocal_rank_fusion(
        [dense, sparse],
        weights=[3.0, 1.0],
    )

    assert get_score(dense_weighted, "shared") > get_score(equal, "shared")


def test_weight_count_must_match_result_lists():
    dense = [result("dense-only")]
    sparse = [result("sparse-only")]

    with pytest.raises(ValueError):
        reciprocal_rank_fusion(
            [dense, sparse],
            weights=[1.0],
        )


def test_zero_weight_removes_source_contribution():
    dense = [result("dense-only")]
    sparse = [result("sparse-only")]

    fused = reciprocal_rank_fusion(
        [dense, sparse],
        weights=[0.0, 1.0],
    )

    dense_score = get_score(fused, "dense-only")
    sparse_score = get_score(fused, "sparse-only")

    assert sparse_score > 0
    assert dense_score == 0.0

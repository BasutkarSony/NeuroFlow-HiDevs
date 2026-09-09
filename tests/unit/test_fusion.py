from pipelines.retrieval.fusion import RetrievalResult, reciprocal_rank_fusion


def r(chunk_id: str) -> RetrievalResult:
    return RetrievalResult(chunk_id=chunk_id, content=chunk_id)


def test_rrf_single_list():
    result = reciprocal_rank_fusion([[r("a"), r("b")]])
    assert [x.chunk_id for x in result] == ["a", "b"]


def test_rrf_combines_lists():
    result = reciprocal_rank_fusion([[r("a")], [r("b")]])
    assert {x.chunk_id for x in result} == {"a", "b"}


def test_rrf_shared_result_ranks_higher():
    result = reciprocal_rank_fusion([[r("a"), r("b")], [r("b"), r("c")]])
    assert result[0].chunk_id == "b"


def test_rrf_scores_are_assigned():
    result = reciprocal_rank_fusion([[r("a")]])
    assert result[0].score == 1 / 61


def test_rrf_preserves_first_result_metadata():
    first = RetrievalResult("a", "first", metadata={"source": "one"})
    second = RetrievalResult("a", "second", metadata={"source": "two"})
    result = reciprocal_rank_fusion([[first], [second]])
    assert result[0].content == "first"

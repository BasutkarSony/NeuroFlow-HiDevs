async def evaluate_context_precision(
    query: str,
    chunks: list[str],
    answer: str,
    judge,
) -> float:
    if not chunks:
        return 0.0

    useful = await judge.check_chunk_usefulness(
        query,
        chunks,
        answer,
    )

    if not useful:
        return 0.0

    weighted_sum = 0.0
    weight_sum = 0.0

    for index, value in enumerate(useful, start=1):
        weight = 1.0 / index
        score = 1.0 if str(value).lower() == "yes" else 0.0

        weighted_sum += score * weight
        weight_sum += weight

    return weighted_sum / weight_sum if weight_sum else 0.0

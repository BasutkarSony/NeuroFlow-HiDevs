from typing import Any


async def evaluate_faithfulness(
    query: str,
    answer: str,
    context: str,
    judge,
) -> float:
    if not answer.strip():
        return 0.0

    claims = await judge.extract_claims(answer)

    if not claims:
        return 1.0

    if not context.strip():
        return 0.0

    scores = await judge.check_claims(
        claims,
        context,
    )

    if not scores:
        return 0.0

    values = {
        "yes": 1.0,
        "partial": 0.5,
        "no": 0.0,
    }

    return sum(
        values.get(str(score).lower(), 0.0)
        for score in scores
    ) / len(scores)

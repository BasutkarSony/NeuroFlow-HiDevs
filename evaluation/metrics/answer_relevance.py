import math


def _cosine(a, b) -> float:
    if not a or not b:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))

    if na == 0 or nb == 0:
        return 0.0

    return max(0.0, min(1.0, dot / (na * nb)))


async def evaluate_answer_relevance(
    query: str,
    answer: str,
    judge,
) -> float:
    if not query.strip() or not answer.strip():
        return 0.0

    questions = await judge.generate_oracle_questions(
        answer,
        count=4,
    )

    if not questions:
        return 0.0

    embeddings = await judge.embed(
        [query] + questions
    )

    original = embeddings[0]

    scores = [
        _cosine(original, embedding)
        for embedding in embeddings[1:]
    ]

    return sum(scores) / len(scores) if scores else 0.0

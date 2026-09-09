import re


async def evaluate_context_recall(
    query: str,
    chunks: list[str],
    answer: str,
    judge,
) -> float:
    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            answer.strip(),
        )
        if sentence.strip()
    ]

    if not sentences:
        return 0.0

    context = "\n\n".join(chunks)

    results = await judge.check_sentence_attribution(
        sentences,
        context,
    )

    if not results:
        return 0.0

    attributable = sum(
        1
        for result in results
        if str(result).lower() == "yes"
    )

    return attributable / len(results)

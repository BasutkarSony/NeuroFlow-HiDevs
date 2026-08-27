import asyncio
from typing import Any

from evaluation.metrics.answer_relevance import (
    evaluate_answer_relevance,
)
from evaluation.metrics.context_precision import (
    evaluate_context_precision,
)
from evaluation.metrics.context_recall import (
    evaluate_context_recall,
)
from evaluation.metrics.faithfulness import (
    evaluate_faithfulness,
)


class EvaluationJudge:
    def __init__(
        self,
        db,
        model_router,
        tracer=None,
    ):
        self.db = db
        self.model_router = model_router
        self.tracer = tracer

    def _evaluation_model(self):
        return self.model_router.get_provider(
            task_type="evaluation"
        )

    async def evaluate(
        self,
        run_id: str,
        query: str,
        answer: str,
        context: str,
        chunks: list[str],
    ) -> dict[str, Any]:

        model = self._evaluation_model()

        class MetricJudge:
            async def extract_claims(self, answer):
                return await model.extract_claims(answer)

            async def check_claims(self, claims, context):
                return await asyncio.gather(
                    *[
                        model.check_claim(
                            claim,
                            context,
                        )
                        for claim in claims
                    ]
                )

            async def generate_oracle_questions(
                self,
                answer,
                count=4,
            ):
                return await model.generate_questions(
                    answer,
                    count=count,
                )

            async def embed(self, texts):
                return await model.embed(texts)

            async def check_chunk_usefulness(
                self,
                query,
                chunks,
                answer,
            ):
                return await asyncio.gather(
                    *[
                        model.check_chunk_usefulness(
                            query,
                            chunk,
                            answer,
                        )
                        for chunk in chunks
                    ]
                )

            async def check_sentence_attribution(
                self,
                sentences,
                context,
            ):
                return await asyncio.gather(
                    *[
                        model.check_sentence_attribution(
                            sentence,
                            context,
                        )
                        for sentence in sentences
                    ]
                )

        judge = MetricJudge()

        results = await asyncio.gather(
            evaluate_faithfulness(
                query,
                answer,
                context,
                judge,
            ),
            evaluate_answer_relevance(
                query,
                answer,
                judge,
            ),
            evaluate_context_precision(
                query,
                chunks,
                answer,
                judge,
            ),
            evaluate_context_recall(
                query,
                chunks,
                answer,
                judge,
            ),
        )

        faithfulness = float(results[0])
        answer_relevance = float(results[1])
        context_precision = float(results[2])
        context_recall = float(results[3])

        overall_score = (
            0.35 * faithfulness
            + 0.30 * answer_relevance
            + 0.20 * context_precision
            + 0.15 * context_recall
        )

        result = {
            "run_id": run_id,
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "overall_score": overall_score,
        }

        if self.tracer is not None:
            with self.tracer.start_as_current_span(
                "evaluation.judge"
            ) as span:
                span.set_attribute(
                    "evaluation.faithfulness",
                    faithfulness,
                )
                span.set_attribute(
                    "evaluation.answer_relevance",
                    answer_relevance,
                )
                span.set_attribute(
                    "evaluation.context_precision",
                    context_precision,
                )
                span.set_attribute(
                    "evaluation.context_recall",
                    context_recall,
                )

        await self._save_evaluation(result)

        if overall_score > 0.8:
            await self._create_training_pair(
                run_id,
                query,
                answer,
                context,
                result,
            )

        return result

    async def _save_evaluation(
        self,
        result: dict[str, Any],
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO evaluations (
                run_id,
                faithfulness,
                answer_relevance,
                context_precision,
                context_recall,
                overall_score,
                metadata
            )
            VALUES (
                $1::uuid,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7::jsonb
            )
            """,
            result["run_id"],
            result["faithfulness"],
            result["answer_relevance"],
            result["context_precision"],
            result["context_recall"],
            result["overall_score"],
            "{}",
        )

    async def _create_training_pair(
        self,
        run_id,
        query,
        answer,
        context,
        result,
    ):
        await self.db.execute(
            """
            UPDATE pipeline_runs
            SET metadata = COALESCE(metadata, '{}'::jsonb)
                || '{"candidate_training_pair": true}'::jsonb
            WHERE id = $1::uuid
            """,
            run_id,
        )

        await self.db.execute(
            """
            INSERT INTO training_pairs (
                run_id,
                query,
                context,
                answer,
                quality_score
            )
            VALUES ($1::uuid, $2, $3, $4, $5)
            """,
            run_id,
            query,
            context,
            answer,
            result["overall_score"],
        )

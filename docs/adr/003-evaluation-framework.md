# ADR 003: Evaluation Framework

## Context

NeuroFlow needs a reliable way to measure the quality of every generated response.

The RAG system must evaluate whether:

- the generated answer is grounded in retrieved context
- the answer addresses the user's question
- retrieved context is relevant and useful
- relevant information was successfully retrieved

The four primary evaluation metrics are:

1. Faithfulness
2. Answer Relevance
3. Context Precision
4. Context Recall

Two main approaches were considered:

1. Human annotation only
2. Automated LLM-as-judge evaluation with human validation

## Decision

NeuroFlow will use **automated LLM-as-judge evaluation as the primary evaluation mechanism**, supplemented by periodic human review and calibration.

Every completed generation will be evaluated asynchronously.

The evaluator will score:

- Faithfulness
- Answer Relevance
- Context Precision
- Context Recall

Evaluation results will be stored in PostgreSQL and used to calculate rolling quality metrics.

Human annotation will remain part of the quality-control process and will be used to:

- validate evaluator accuracy
- detect evaluator drift
- investigate unusual results
- calibrate evaluation prompts
- create trusted benchmark datasets

## Why Automated Evaluation

Human evaluation provides high-quality judgments but does not scale efficiently to every production query.

NeuroFlow is designed to evaluate potentially large numbers of generations. Manually reviewing every response would introduce:

- high operational cost
- significant latency
- inconsistent evaluation frequency
- limited scalability

LLM-as-judge evaluation provides a practical mechanism for evaluating every generation asynchronously while maintaining the ability to use human reviewers for validation.

## Evaluation Flow

```mermaid
flowchart TB
    Generation["Completed Generation"]
    Queue["Async Evaluation Queue"]
    Judge["LLM-as-Judge"]

    Faithfulness["Faithfulness"]
    Relevance["Answer Relevance"]
    Precision["Context Precision"]
    Recall["Context Recall"]

    Human["Periodic Human Review"]
    Compare["Judge vs Human Comparison"]
    Store[("PostgreSQL")]
    Aggregate["Rolling Metrics"]

    Generation --> Queue
    Queue --> Judge

    Judge --> Faithfulness
    Judge --> Relevance
    Judge --> Precision
    Judge --> Recall

    Faithfulness --> Store
    Relevance --> Store
    Precision --> Store
    Recall --> Store

    Store --> Aggregate

    Store --> Human
    Human --> Compare
    Judge --> Compare
Evaluation Inputs

The evaluator receives the information necessary to judge the generation:

user query
generated answer
retrieved context
citations
pipeline configuration
evaluation criteria

The evaluator must distinguish between the retrieved evidence and the generated answer.

Metric Definitions
1. Faithfulness

Faithfulness measures whether claims in the generated answer are supported by the retrieved context.

A high score indicates that the answer is grounded in the available evidence.

A low score indicates that the answer contains unsupported claims or possible hallucinations.

2. Answer Relevance

Answer relevance measures whether the generated answer directly addresses the user's question.

A response can be grounded in retrieved information but still be irrelevant to the user's actual request.

3. Context Precision

Context precision measures whether the retrieved chunks are relevant to producing the answer.

A low score indicates that retrieval returned excessive irrelevant context.

4. Context Recall

Context recall measures whether the retrieval system successfully retrieved the relevant information required to answer the question.

A low score indicates that relevant information may exist in the knowledge base but was not retrieved.

Scoring

Evaluation metrics will use normalized scores from:

0.0 = poor
1.0 = excellent

The system will store the individual metric scores rather than only a single combined score.

This allows retrieval and generation problems to be diagnosed independently.

LLM-as-Judge Failure Modes

Automated evaluation introduces several possible failure modes.

Judge Bias

The evaluator may systematically prefer certain response styles or models.

Position Bias

The evaluator may favor information appearing earlier or later in the evaluation input.

Prompt Sensitivity

Small changes to the evaluation prompt may change the score.

Model Bias

An evaluator may produce biased results when judging generations from another model or provider.

Hallucinated Evaluation

The evaluator itself may make unsupported judgments.

Score Compression

The evaluator may produce scores concentrated around a narrow range instead of meaningfully distinguishing quality levels.

Correlated Model Errors

If the same model family is used for generation and evaluation, shared weaknesses may cause the evaluator to miss generation errors.

Failure Detection

NeuroFlow will detect evaluation problems through several mechanisms.

Human Calibration

A representative sample of evaluated generations will be reviewed by humans.

Human scores will be compared with automated scores.

Large disagreements will be investigated.

Benchmark Dataset

A fixed evaluation benchmark containing manually reviewed examples will be maintained.

Changes to the evaluation system will be tested against this benchmark.

Evaluator Versioning

Every evaluation record will store the evaluator model and evaluator version.

This allows changes in evaluation behavior to be detected over time.

Distribution Monitoring

The system will monitor metric distributions for unexpected changes such as:

sudden score increases
sudden score decreases
unusually narrow score ranges
significant disagreement with human ratings
Agreement Monitoring

Human and automated scores will be compared using appropriate agreement statistics and threshold-based analysis.

Repeated disagreement indicates that the evaluation prompt, evaluator model, or evaluation criteria may require revision.

Human Evaluation Policy

Human review will not be required for every production generation.

Instead, human review will be performed on:

randomly sampled generations
low-scoring generations
high-impact generations
evaluator disagreement cases
benchmark examples
suspected evaluator failures

This provides scalable evaluation while maintaining a human quality-control layer.

Evaluation Data Storage

Each evaluation record will contain:

evaluation ID
query ID
generation ID
pipeline ID
evaluator model
evaluator version
faithfulness score
answer relevance score
context precision score
context recall score
optional human rating
evaluation timestamp

This information enables historical analysis and evaluator comparisons.

Consequences
Positive Consequences
Every completed generation can be evaluated asynchronously.
Evaluation scales with production traffic.
Quality metrics can be calculated continuously.
Retrieval and generation problems can be analyzed separately.
Human reviewers can focus on difficult or high-value cases.
Evaluation results can support fine-tuning dataset selection.
Evaluator versions can be tracked for reproducibility.
Negative Consequences
LLM-as-judge evaluation is not perfectly reliable.
Evaluation introduces additional model usage and cost.
Evaluator bias can affect reported metrics.
Human calibration remains necessary.
Evaluation prompts require careful design and maintenance.
Different evaluator models may produce different scores.
Quality Control Strategy

NeuroFlow will use a layered evaluation strategy:

Production Generation
        ↓
Automated LLM-as-Judge
        ↓
Metric Storage
        ↓
Rolling Quality Monitoring
        ↓
Sampling / Low-Score Detection
        ↓
Human Review
        ↓
Evaluator Calibration
        ↓
Updated Evaluation Strategy

This approach combines the scalability of automated evaluation with the reliability of human validation.

Future Evolution

The evaluation framework can be extended with:

additional RAGAS metrics
domain-specific evaluation criteria
task-specific evaluators
multiple independent judges
human feedback collection
pairwise model comparison
regression benchmarks

Any new evaluation metric must be versioned and documented so historical results remain interpretable.

Status

Accepted

Date

2026-08-25
# ADR 004: Model Routing Strategy

## Context

NeuroFlow supports multiple LLM providers and model tiers.

Different queries have different requirements. Some queries require strong reasoning or domain capability, while others prioritize low latency and low cost.

Using the same model for every request can increase cost and latency without improving answer quality.

The model routing layer must therefore select an appropriate model based on:

- Query complexity
- Required capability
- Domain
- Latency requirements
- Cost
- Context length
- Availability of a specialized fine-tuned model

The routing decision must also be observable and reproducible so that model performance can be evaluated over time.

## Decision

NeuroFlow will use a **rule-based model routing strategy with configurable scoring**.

The router will first classify the request and determine its requirements.

The routing process will consider:

1. Query complexity
2. Domain
3. Required reasoning capability
4. Context size
5. Latency requirement
6. Cost sensitivity
7. Fine-tuned model availability
8. Provider availability

The router will select the lowest-cost model that satisfies the required quality and capability constraints.

If the selected model is unavailable, the router will fall back to the next eligible model tier.

## Model Tiers

NeuroFlow will initially define three logical model tiers.

### Tier 1 — Fast / Low Cost

Designed for:

- Simple factual questions
- Short summaries
- Basic classification
- Simple transformations
- High-volume requests
- Low-latency workloads

Priority:

```text
Cost → Latency → Capability
Tier 2 — Balanced

Designed for:

Standard RAG questions
Multi-document questions
Moderate reasoning
General knowledge retrieval
Customer-support workloads
Typical production queries

Priority:

Capability → Cost → Latency
Tier 3 — Advanced / High Capability

Designed for:

Complex reasoning
Multi-step analysis
Difficult synthesis
Ambiguous questions
Technical analysis
High-value requests where answer quality is more important than cost

Priority:

Capability → Quality → Cost → Latency
Routing Matrix
Query Type	Preferred Tier	Primary Reason
Simple factual query	Tier 1	Low cost and low latency
Short summarization	Tier 1	Simple generation
Classification	Tier 1	High-volume, predictable task
Standard RAG query	Tier 2	Balanced quality and cost
Multi-document RAG	Tier 2	Stronger context handling
Customer-support query	Tier 2	Consistent grounded responses
Moderate reasoning	Tier 2	Balanced reasoning capability
Complex reasoning	Tier 3	Higher reasoning capability
Multi-step analysis	Tier 3	Advanced reasoning
Complex technical query	Tier 3	Higher capability
High-value decision support	Tier 3	Quality prioritized
Specialized domain query with better fine-tuned model	Fine-tuned model	Domain specialization
Routing Decision Flow
Routing Score

Each eligible model can receive a routing score based on normalized factors.

Conceptually:

Routing Score =
    Capability Weight × Capability Score
    + Quality Weight × Quality Score
    + Latency Weight × Latency Score
    + Cost Weight × Cost Score
    + Domain Weight × Domain Score

The weights are configurable by pipeline.

For cost-sensitive pipelines, cost receives a higher weight.

For quality-sensitive pipelines, capability and quality receive higher weights.

The router must never select a model that violates a hard requirement such as unsupported modality or insufficient context length.

Fine-Tuned Model Routing

Fine-tuned models are eligible for routing only after evaluation against their corresponding base model.

A fine-tuned model may be preferred when:

it is trained for the relevant domain
it has sufficient evaluation data
faithfulness meets the configured threshold
answer relevance meets the configured threshold
it outperforms the base model
latency and cost remain acceptable

The fine-tuned model is not automatically promoted after training.

Promotion requires evaluation evidence.

Fallback Strategy

If the preferred model is unavailable, the router follows the configured fallback chain.

Example:

Tier 2 Model
    ↓ unavailable
Tier 1 Model
    ↓ unavailable
Tier 3 Model
    ↓ unavailable
Return MODEL_UNAVAILABLE

Fallback behavior is configurable per pipeline.

A fallback decision is logged as part of the generation metadata.

Domain Routing

Domain information may be inferred from:

pipeline configuration
metadata filters
query classification
selected knowledge base
fine-tuned model capabilities

Example:

Domain	Preferred Model
General knowledge	Tier 2
Customer support	Customer-support fine-tuned model
Technical documentation	Tier 2 or Tier 3
Complex engineering analysis	Tier 3
High-volume simple FAQ	Tier 1

Domain routing must not override hard safety, context, or capability requirements.

Latency-Aware Routing

Latency-sensitive requests may prefer Tier 1 when the expected quality difference is acceptable.

The router will track:

model response latency
time to first token
token generation speed
timeout frequency

Historical latency can be used as an input to future routing decisions.

Cost-Aware Routing

The router records estimated model usage and cost for every generation.

Cost-aware routing prevents expensive models from being used unnecessarily for simple requests.

The system may apply configurable cost budgets at the pipeline or request level.

If a request cannot meet its required quality within the configured budget, the router may select a higher-cost model only when the pipeline allows it.

Observability

Every routing decision will record:

query ID
pipeline ID
selected model
model tier
provider
routing reason
routing score
fallback status
estimated cost
latency
model outcome

This information enables analysis of routing effectiveness.

Routing Evaluation

The routing strategy will be evaluated using:

Faithfulness
Answer Relevance
Context Precision
Context Recall
Latency
Cost per request
Error rate
User rating

Routing changes should be based on measured performance rather than assumptions.

Consequences
Positive Consequences
Simple queries can use inexpensive models.
Complex queries can access stronger models.
Domain-specific fine-tuned models can be utilized.
Latency and cost can be controlled.
Model providers can be changed without changing API contracts.
Routing decisions are observable.
Fallback behavior improves availability.
Routing policies can be changed through pipeline configuration.
Negative Consequences
Routing adds classification and decision-making complexity.
Incorrect query classification can select an unsuitable model.
More models require additional monitoring.
Routing scores require calibration.
Model availability and pricing can change over time.
Fine-tuned models require continuous evaluation before promotion.
Future Evolution

The initial implementation will use configurable rules and scoring.

Future versions may introduce:

learned routing
historical performance-based routing
contextual bandits
cost-quality optimization
provider-specific routing
automatic model benchmarking
dynamic routing based on real-time provider latency

Any future routing strategy must preserve the same observability and evaluation requirements.

Status

Accepted

Date

2026-08-25
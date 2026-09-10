from dataclasses import dataclass
from typing import Any

@dataclass
class Document:
    id: str
    status: str
    data: dict[str, Any]

@dataclass
class QueryResult:
    run_id: str
    answer: str
    data: dict[str, Any]

@dataclass
class EvaluationResult:
    id: str
    run_id: str
    data: dict[str, Any]

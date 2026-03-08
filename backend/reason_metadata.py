from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReasonMeta:
    confidence: int
    evidence_urls: list[str] = field(default_factory=list)

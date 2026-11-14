"""Gestion des signalements (module signalement_manager).

Un signalement réactive une zone déjà explorée : c'est le mécanisme central
de la revisite (exigence F07).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

PENDING = "pending"
ASSIGNED = "assigned"
INVESTIGATING = "investigating"
RESOLVED = "resolved"
EXPIRED = "expired"

VALID_STATES = (PENDING, ASSIGNED, INVESTIGATING, RESOLVED, EXPIRED)

_ids = itertools.count(1)


@dataclass
class Signalement:
    """Signalement d'une activité suspecte dans une zone."""

    id: str
    zone_id: int
    timestamp: int
    status: str = PENDING
    priority: int = 1
    confidence: float = 1.0
    assigned_to: set[str] = field(default_factory=set)
    required_officers: int = 1

    def age(self, step: int) -> int:
        return step - self.timestamp


class SignalementManager:
    """Cycle de vie des signalements : création, attribution, résolution, expiration."""

    def __init__(self, ttl: int = 60):
        self.ttl = ttl
        self.signals: dict[str, Signalement] = {}

    def create(self, zone_id: int, step: int, priority: int = 1,
               confidence: float = 1.0, required_officers: int = 1,
               source: str = "system") -> Signalement:
        sig = Signalement(
            id=f"SIG-{next(_ids):04d}",
            zone_id=zone_id,
            timestamp=step,
            priority=priority,
            confidence=confidence,
            required_officers=required_officers,
        )
        sig.source = source
        self.signals[sig.id] = sig
        return sig

    def pending(self, step: int) -> list[Signalement]:
        self.expire(step)
        return [s for s in self.signals.values() if s.status in (PENDING, ASSIGNED, INVESTIGATING)]

    def assign(self, signal_id: str, agent_id: str) -> None:
        sig = self.signals[signal_id]
        sig.assigned_to.add(agent_id)
        sig.status = ASSIGNED if len(sig.assigned_to) < sig.required_officers else INVESTIGATING

    def investigate(self, signal_id: str) -> None:
        self.signals[signal_id].status = INVESTIGATING

    def resolve(self, signal_id: str) -> None:
        self.signals[signal_id].status = RESOLVED

    def expire(self, step: int) -> None:
        for sig in self.signals.values():
            if sig.status in (PENDING, ASSIGNED, INVESTIGATING) and sig.age(step) > self.ttl:
                sig.status = EXPIRED

    def signals_for_zone(self, zone_id: int, step: int) -> list[Signalement]:
        return [s for s in self.pending(step) if s.zone_id == zone_id]

    def relevance(self, sig: Signalement, step: int) -> float:
        """Pertinence S(z) d'un signalement : priorité x confiance x fraîcheur."""
        freshness = max(0.0, 1.0 - sig.age(step) / max(1, self.ttl))
        return sig.priority * sig.confidence * (0.4 + 0.6 * freshness)

    def broadcast(self) -> list[Signalement]:
        """Signalements visibles par les agents (canal radio policier)."""
        return [s for s in self.signals.values() if s.status in (PENDING, ASSIGNED, INVESTIGATING)]

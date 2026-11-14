"""Mémoire spatiale individuelle des agents stratégiques (module spatial_memory).

Chaque agent policier ou fugitif possède sa propre mémoire, conservée pendant
toute la durée de vie de l'agent. Elle n'est jamais réinitialisée entre deux
décisions : c'est ce qui permet l'exploration méthodique et la revisite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UNKNOWN = "inconnue"
EXPLORED = "explorée"
TO_REVISIT = "à revisiter"


@dataclass
class ZoneKnowledge:
    """Connaissance d'un agent sur une zone précise."""

    state: str = UNKNOWN
    last_visit_step: int | None = None
    visit_count: int = 0
    danger_level: float = 0.0
    police_presence: float = 0.0


@dataclass
class SpatialMemory:
    """Mémoire spatiale individuelle d'un agent stratégique.

    Attributs :
        visited_zones       : zones explorées au moins une fois.
        unvisited_zones     : zones jamais vues (connaissance déclarative de la carte).
        current_zone        : zone où se trouve l'agent.
        exploration_history : historique ordonné des zones visitées.
        known_signals       : signalements connus de l'agent.
        known_dangers       : zones dangereuses observées {zone_id: niveau}.
        last_position       : dernière position cellule de l'agent.
        last_target         : dernière destination choisie.
        rng_seed_state      : répartition des zones entre agents (secteur assigné).
        assigned_sector     : secteur principal attribué par la coordination.
    """

    all_zone_ids: set[int] = field(default_factory=set)
    visited_zones: set[int] = field(default_factory=set)
    unvisited_zones: set[int] = field(default_factory=set)
    current_zone: int | None = None
    exploration_history: list[int] = field(default_factory=list)
    known_signals: list[dict] = field(default_factory=list)
    known_dangers: dict[int, float] = field(default_factory=dict)
    last_position: tuple[int, int] | None = None
    last_target: int | None = None
    assigned_sector: int | None = None
    knowledge: dict[int, ZoneKnowledge] = field(default_factory=dict)

    def discover_map(self, zone_ids: set[int]) -> None:
        """Enregistre la liste des zones existantes (sans connaître leur contenu)."""
        self.all_zone_ids = set(zone_ids)
        self.unvisited_zones = set(zone_ids) - self.visited_zones
        for zid in zone_ids:
            self.knowledge.setdefault(zid, ZoneKnowledge())

    def visit_zone(self, zone_id: int, step: int) -> None:
        k = self.knowledge.setdefault(zone_id, ZoneKnowledge())
        k.state = EXPLORED
        k.last_visit_step = step
        k.visit_count += 1
        k.danger_level *= 0.9
        self.visited_zones.add(zone_id)
        self.unvisited_zones.discard(zone_id)
        self.current_zone = zone_id
        self.exploration_history.append(zone_id)

    def mark_to_revisit(self, zone_id: int) -> None:
        k = self.knowledge.setdefault(zone_id, ZoneKnowledge())
        if k.state == EXPLORED:
            k.state = TO_REVISIT

    def add_signal(self, signal: dict) -> None:
        self.known_signals.append(signal)
        self.mark_to_revisit(signal["zone_id"])

    def resolve_signal(self, signal_id: str) -> None:
        for s in self.known_signals:
            if s["id"] == signal_id:
                s["status"] = "resolved"

    def add_danger(self, zone_id: int, level: float) -> None:
        k = self.knowledge.setdefault(zone_id, ZoneKnowledge())
        k.danger_level = min(1.0, k.danger_level + level)
        self.known_dangers[zone_id] = k.danger_level

    def danger_of(self, zone_id: int) -> float:
        return self.knowledge.get(zone_id, ZoneKnowledge()).danger_level

    def state_of(self, zone_id: int) -> str:
        return self.knowledge.get(zone_id, ZoneKnowledge()).state

    def has_unvisited_zones(self) -> bool:
        return len(self.unvisited_zones) > 0

    def pending_signals(self) -> list[dict]:
        return [s for s in self.known_signals if s.get("status") in ("pending", "assigned", "investigating")]

    def exploration_ratio(self) -> float:
        if not self.all_zone_ids:
            return 0.0
        return len(self.visited_zones) / len(self.all_zone_ids)

    def recently_visited(self, zone_id: int, step: int, window: int = 10) -> bool:
        k = self.knowledge.get(zone_id)
        return bool(k and k.last_visit_step is not None and step - k.last_visit_step <= window)

"""Organisation de l'exploration (module exploration_manager).

Suit la couverture globale et par agent, et détecte la fin d'exploration
(Test 1 de la spécification).
"""

from __future__ import annotations


class ExplorationManager:
    """Statistiques de couverture et historique des explorations."""

    def __init__(self, zone_manager):
        self.zone_manager = zone_manager
        self.history: list[dict] = []

    def coverage_of(self, agent) -> float:
        return agent.memory.exploration_ratio()

    def global_coverage(self, strategic_agents) -> float:
        """Proportion de zones visitées par au moins un agent stratégique."""
        all_zones = set(self.zone_manager.zones)
        visited: set[int] = set()
        for a in strategic_agents:
            visited |= a.memory.visited_zones
        return len(visited) / len(all_zones) if all_zones else 0.0

    def exploration_complete(self, agent) -> bool:
        return not agent.memory.has_unvisited_zones()

    def record(self, step: int, agent_id: str, zone_id: int, event: str) -> None:
        self.history.append({
            "step": step, "agent": agent_id, "zone": zone_id, "event": event,
        })

    def zone_visit_counts(self, strategic_agents) -> dict[int, int]:
        counts: dict[int, int] = {z: 0 for z in self.zone_manager.zones}
        for a in strategic_agents:
            for z in a.memory.visited_zones:
                counts[z] = counts.get(z, 0) + 1
        return counts

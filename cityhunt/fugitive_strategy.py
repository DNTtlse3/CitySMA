"""Stratégie des fugitifs sur le réseau OSM (module fugitive_strategy).

Cycle de décision avec priorité supplémentaire : réaction aux dangers observés.
Le fugitif n'utilise que ses observations et sa mémoire (exigence F12).
"""

from __future__ import annotations

from .osm_network import haversine_m
from .spatial_memory import TO_REVISIT


class FugitiveStrategy:
    role = "fugitive"

    PANIC_RADIUS_M = 300.0

    def __init__(self, decision_engine):
        self.engine = decision_engine

    def decide(self, agent, model) -> None:
        memory = agent.memory

        visible_police = model.visible_police(agent)
        if visible_police:
            nearest = min(visible_police, key=lambda p: self._dist(agent, p, model))
            if self._dist(agent, nearest, model) <= self.PANIC_RADIUS_M:
                agent.rl.reward("detection", model.zones.zone_of(agent.position), model.step_count)
                if self._flee(agent, model, nearest):
                    return

        candidates = {
            z for z in memory.unvisited_zones
            if memory.danger_of(z) < 0.5 and model.zones.nodes_in_zone(z)
        }
        if candidates:
            self._goto_best(agent, model, candidates)
            return

        revisit = {
            z for z in memory.all_zone_ids
            if memory.state_of(z) in (TO_REVISIT, "explorée")
            and memory.danger_of(z) < 0.4
            and z != memory.current_zone
            and model.zones.nodes_in_zone(z)
        }
        if revisit:
            self._goto_best(agent, model, revisit)
            return
        agent.set_path([])

    # ------------------------------------------------------------------ #

    @staticmethod
    def _dist(a, b, model) -> float:
        return haversine_m(model.network.coords(a.position), model.network.coords(b.position))

    def _flee(self, agent, model, nearest_police) -> bool:
        """Fuite : zone voisine la plus sûre et la plus éloignée du policier."""
        memory = agent.memory
        current = model.zones.zone_of(agent.position)
        options = set(model.zones.zones[current].neighbors) | {current}
        px, py = model.network.coords(nearest_police.position)

        best_zone, best_score = None, float("-inf")
        for zid in options:
            if not model.zones.nodes_in_zone(zid):
                continue
            zlat, zlon = model.zones.zone_centroid(zid)
            score = haversine_m((zlat, zlon), (px, py)) / 100.0 - 20.0 * memory.danger_of(zid)
            if zid == current:
                score -= 3.0
            if score > best_score:
                best_zone, best_score = zid, score
        if best_zone is None:
            return False

        target = model.zones.farthest_zone_node_from(best_zone, (px, py))
        if target is None:
            return False
        path = model.pathfinder.find_path(agent.position, target, memory.known_dangers)
        if path is None:
            return False
        agent.set_path(path)
        agent.memory.last_target = best_zone
        agent.target_zone = best_zone
        return True

    def _goto_best(self, agent, model, candidates: set[int]) -> None:
        memory = agent.memory
        here = model.zones.zone_of(agent.position)
        distances = {z: model.zones.distance(here, z) / 1000.0 for z in candidates}
        ranked = self.engine.rank_zones(self.role, memory, model.step_count, distances, candidates)
        for zid, _score in ranked:
            target = model.zones.nearest_zone_node(zid, model.network.coords(agent.position))
            if target is None:
                continue
            path = model.pathfinder.find_path(agent.position, target, memory.known_dangers)
            if path is None:
                continue
            agent.set_path(path)
            agent.memory.last_target = zid
            agent.target_zone = zid
            return
        agent.set_path([])

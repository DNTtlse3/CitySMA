"""Stratégie des fugitifs (module fugitive_strategy).

Cycle de décision avec priorité supplémentaire : réaction aux dangers observés.
Le fugitif n'utilise que ses observations et sa mémoire (exigence F12).
"""

from __future__ import annotations

from .spatial_memory import TO_REVISIT, UNKNOWN


class FugitiveStrategy:
    role = "fugitive"

    PANIC_RADIUS = 6

    def __init__(self, decision_engine):
        self.engine = decision_engine

    def decide(self, agent, env) -> None:
        memory = agent.memory
        step = env.step_count

        visible_police = env.visible_police(agent)
        if visible_police:
            nearest = min(
                visible_police,
                key=lambda p: abs(p.position[0] - agent.position[0]) + abs(p.position[1] - agent.position[1]),
            )
            dist = abs(nearest.position[0] - agent.position[0]) + abs(nearest.position[1] - agent.position[1])
            if dist <= self.PANIC_RADIUS:
                agent.rl.reward("detection")
                if self._flee(agent, env, nearest):
                    return

        candidates = {
            z for z in memory.unvisited_zones
            if memory.danger_of(z) < 0.5 and env.zone_manager.free_cells(z)
        }
        if candidates:
            self._goto_best(agent, env, candidates, step)
            return

        revisit = {
            z for z in memory.all_zone_ids
            if memory.state_of(z) in (TO_REVISIT, "explorée")
            and memory.danger_of(z) < 0.4
            and z != memory.current_zone
        }
        if revisit:
            self._goto_best(agent, env, revisit, step)
            return
        agent.set_path([])

    # ------------------------------------------------------------------ #

    def _flee(self, agent, env, nearest_police) -> bool:
        """Fuite : choisir la zone voisine la plus sûre et la plus éloignée de la police."""
        memory = agent.memory
        current = memory.current_zone
        if current is None:
            return False
        options = set(env.zone_manager.zones[current].neighbors) | {current}
        px, py = nearest_police.position

        best_zone, best_score = None, float("-inf")
        for zid in options:
            if not env.zone_manager.free_cells(zid):
                continue
            zx, zy = env.zone_manager.zones[zid].position
            dist_police = abs(zx - px) + abs(zy - py)
            danger = memory.danger_of(zid)
            score = dist_police - 20.0 * danger
            if zid == current:
                score -= 3.0
            if score > best_score:
                best_zone, best_score = zid, score
        if best_zone is None:
            return False

        target_cell = env.farthest_free_cell_from(best_zone, px, py)
        path = env.path_to(agent, target_cell)
        if path is None:
            return False
        agent.set_path(path)
        agent.memory.last_target = best_zone
        agent.target_zone = best_zone
        return True

    def _goto_best(self, agent, env, candidates: set[int], step: int) -> None:
        memory = agent.memory
        distances = {
            zid: env.zone_manager.distance(memory.current_zone, zid) if memory.current_zone is not None else 0.0
            for zid in candidates
        }
        ranked = self.engine.rank_zones(self.role, memory, step, distances, candidates)
        for zid, _score in ranked:
            target_cell = env.best_entry_cell(agent, zid)
            path = env.path_to(agent, target_cell)
            if path is None:
                continue
            agent.set_path(path)
            agent.memory.last_target = zid
            agent.target_zone = zid
            return
        agent.set_path([])

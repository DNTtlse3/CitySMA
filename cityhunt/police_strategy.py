"""Stratégie policière (module police_strategy).

Cycle de décision (spécification §11) :
    1. Observation déjà réalisée par l'environnement.
    2. Signalement prioritaire attribué -> investigation.
    3. Fugitif visible -> poursuite directe (observation légitime).
    4. Zones inconnues accessibles -> exploration prioritaire.
    5. Sinon -> revisite / patrouille organisée.
"""

from __future__ import annotations

from .spatial_memory import TO_REVISIT, UNKNOWN


class PoliceStrategy:
    role = "police"

    def __init__(self, decision_engine):
        self.engine = decision_engine

    def decide(self, agent, env) -> None:
        memory = agent.memory
        step = env.step_count
        coord = env.coordination

        signal = self._priority_signal(agent, env)
        if signal is not None:
            target_zone = signal.zone_id
            if coord.claim_zone(target_zone, agent.id):
                agent.current_signal = signal.id
                self._goto(agent, env, target_zone, step)
                return
        agent.current_signal = None

        visible_fugitives = env.visible_fugitives(agent)
        if visible_fugitives:
            target_cell = visible_fugitives[0].position
            agent.set_path(env.path_to(agent, target_cell))
            return

        candidates = self._exploration_candidates(agent, env)
        if candidates:
            self._goto_best(agent, env, candidates, step)
            return

        self._patrol_or_revisit(agent, env, step)

    # ------------------------------------------------------------------ #

    def _priority_signal(self, agent, env):
        """Signalement prioritaire : déjà attribué à cet agent, ou à récupérer."""
        assigned = env.signalements.pending(env.step_count)
        mine = [s for s in assigned if env.coordination.signal_assigned_to(s.id) == agent.id]
        if mine:
            mine.sort(key=lambda s: (-s.priority, s.timestamp))
            return mine[0]
        return env.coordination.take_unassigned_signal(agent.id, env.step_count)

    def _exploration_candidates(self, agent, env) -> set[int]:
        """Zones inconnues accessibles, non revendiquées par un autre policier."""
        memory = agent.memory
        return {
            z for z in memory.unvisited_zones
            if not env.coordination.is_claimed_by_other(z, agent.id)
            and env.zone_manager.free_cells(z)
        }

    def _goto_best(self, agent, env, candidates: set[int], step: int) -> None:
        memory = agent.memory
        distances = {
            zid: env.zone_manager.distance(memory.current_zone, zid) if memory.current_zone is not None else 0.0
            for zid in candidates
        }
        ranked = self.engine.rank_zones(self.role, memory, step, distances, candidates)
        for zid, _score in ranked:
            if self._goto(agent, env, zid, step):
                return
        self._patrol_or_revisit(agent, env, step)

    def _goto(self, agent, env, zone_id: int, step: int) -> bool:
        """Calcule l'itinéraire A* vers la zone ; retourne True si un chemin existe."""
        target_cell = env.best_entry_cell(agent, zone_id)
        path = env.path_to(agent, target_cell)
        if path is None:
            return False
        agent.set_path(path)
        agent.memory.last_target = zone_id
        agent.target_zone = zone_id
        return True

    def _patrol_or_revisit(self, agent, env, step: int) -> None:
        """Toutes les zones sont explorées : revisite motivée ou patrouille."""
        memory = agent.memory
        revisit = {
            z for z in memory.all_zone_ids
            if memory.state_of(z) == TO_REVISIT
            and not env.coordination.is_claimed_by_other(z, agent.id)
        }
        if revisit:
            self._goto_best(agent, env, revisit, step)
            return

        sector = env.coordination.sector_of(agent.id)
        pool = set(memory.all_zone_ids) - {memory.current_zone}
        if sector is not None and sector in pool:
            pool = {sector} | set(env.zone_manager.zones[sector].neighbors)
            pool &= set(memory.all_zone_ids)
        if not pool:
            pool = set(memory.all_zone_ids)
        distances = {
            zid: env.zone_manager.distance(memory.current_zone, zid) if memory.current_zone is not None else 0.0
            for zid in pool
        }
        ranked = self.engine.rank_zones(self.role, memory, step, distances, pool)
        for zid, _score in ranked:
            if self._goto(agent, env, zid, step):
                return
        agent.set_path([])

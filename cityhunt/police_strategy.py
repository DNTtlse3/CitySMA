"""Stratégie policière sur le réseau OSM (module police_strategy).

Cycle de décision (spécification §11) :
    1. Observation déjà réalisée par le modèle Mesa.
    2. Signalement prioritaire attribué -> investigation.
    3. Fugitif visible -> poursuite directe (observation légitime).
    4. Zones inconnues accessibles -> exploration prioritaire.
    5. Sinon -> revisite / patrouille du secteur assigné.
"""

from __future__ import annotations

from .spatial_memory import TO_REVISIT


class PoliceStrategy:
    role = "police"

    def __init__(self, decision_engine):
        self.engine = decision_engine

    def decide(self, agent, model) -> None:
        memory = agent.memory
        step = model.step_count
        coord = model.coordination

        signal = self._priority_signal(agent, model)
        if signal is not None:
            if coord.claim_zone(signal.zone_id, agent.name):
                agent.current_signal = signal.id
                self._goto(agent, model, signal.zone_id)
                return
        agent.current_signal = None

        visible = model.visible_fugitives(agent)
        if visible:
            agent.set_path(model.pathfinder.find_path(
                agent.position, visible[0].position, memory.known_dangers) or [])
            return

        candidates = {
            z for z in memory.unvisited_zones
            if model.zones.nodes_in_zone(z)
            and not coord.is_claimed_by_other(z, agent.name)
        }
        if candidates:
            self._goto_best(agent, model, candidates)
            return

        self._patrol_or_revisit(agent, model)

    # ------------------------------------------------------------------ #

    def _priority_signal(self, agent, model):
        assigned = model.signalements.pending(model.step_count)
        mine = [s for s in assigned if model.coordination.signal_assigned_to(s.id) == agent.name]
        if mine:
            mine.sort(key=lambda s: (-s.priority, s.timestamp))
            return mine[0]
        return model.coordination.take_unassigned_signal(agent.name, model.step_count)

    def _goto_best(self, agent, model, candidates: set[int]) -> None:
        memory = agent.memory
        here = model.zones.zone_of(agent.position)
        distances = {z: model.zones.distance(here, z) / 1000.0 for z in candidates}
        ranked = self.engine.rank_zones(self.role, memory, model.step_count, distances, candidates)
        for zid, _score in ranked:
            if self._goto(agent, model, zid):
                return
        self._patrol_or_revisit(agent, model)

    def _goto(self, agent, model, zone_id: int) -> bool:
        target = model.zones.nearest_zone_node(zone_id, model.network.coords(agent.position))
        if target is None:
            return False
        path = model.pathfinder.find_path(agent.position, target, agent.memory.known_dangers)
        if path is None:
            return False
        agent.set_path(path)
        agent.memory.last_target = zone_id
        agent.target_zone = zone_id
        return True

    def _patrol_or_revisit(self, agent, model) -> None:
        memory = agent.memory
        revisit = {
            z for z in memory.all_zone_ids
            if memory.state_of(z) == TO_REVISIT
            and not model.coordination.is_claimed_by_other(z, agent.name)
            and model.zones.nodes_in_zone(z)
        }
        if revisit:
            self._goto_best(agent, model, revisit)
            return

        sector = model.coordination.sector_of(agent.name)
        pool = set(memory.all_zone_ids) - {memory.current_zone}
        if sector is not None and sector in pool:
            pool = ({sector} | set(model.zones.zones[sector].neighbors)) & set(memory.all_zone_ids)
        pool = {z for z in pool if model.zones.nodes_in_zone(z)}
        if not pool:
            pool = {z for z in memory.all_zone_ids if model.zones.nodes_in_zone(z)}
        if not pool:
            agent.set_path([])
            return
        self._goto_best(agent, model, pool)

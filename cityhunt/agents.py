"""Agents Mesa de CityHunt (module agents).

Chaque agent assemble : mémoire spatiale individuelle, stratégie de rôle,
module RL et itinéraire courant. La perception est fournie par le modèle ;
aucun agent ne voit au-delà de son rayon de perception (F12).
"""

from __future__ import annotations

from mesa import Agent

from .rl_module import RLModule
from .spatial_memory import SpatialMemory


class CityAgent(Agent):
    """Agent de base : position = nœud du réseau de rues."""

    def __init__(self, model, name: str, role: str, node, speed: int = 2,
                 perception_m: float = 250.0, strategy=None):
        super().__init__(model)
        self.name = name
        self.role = role
        self.position = node
        self.speed = speed
        self.perception_m = perception_m
        self.memory = SpatialMemory()
        self.rl = RLModule(role, enabled=model.rl_enabled)
        self.strategy = strategy
        self.path: list = []
        self.target_zone: int | None = None
        self.current_signal: str | None = None
        self.alive = True
        self.last_seen_threat_step: int | None = None
        self.zone_manager = model.zones

    @property
    def is_strategic(self) -> bool:
        return self.role in ("police", "fugitive")

    def set_path(self, path: list) -> None:
        self.path = list(path)

    @property
    def current_zone(self) -> int:
        return self.zone_manager.zone_of(self.position)

    def coords(self) -> tuple[float, float]:
        return self.model.network.coords(self.position)

    # ------------------------------------------------------------------ #
    # Cycle Mesa : perceive -> act                                        #
    # ------------------------------------------------------------------ #

    def perceive(self) -> None:
        model = self.model
        if self.role == "police":
            seen = model.visible_fugitives(self)
            if seen:
                self.last_seen_threat_step = model.step_count
                zone = model.zones.zone_of(seen[0].position)
                model.coordination.share_observation(
                    self.name, zone, model.step_count, "fugitive_seen")
                if model.random.random() < 0.35:
                    model.signalements.create(zone, model.step_count, priority=2,
                                              confidence=0.9, source=self.name)
        elif self.role == "fugitive":
            seen = model.visible_police(self)
            if seen:
                self.last_seen_threat_step = model.step_count
                self.memory.add_danger(self.current_zone, 0.4)

    def act(self) -> None:
        if not self.alive:
            return
        model = self.model
        if self.is_strategic:
            mover = model.movement
            if not self.path or not mover.route_is_valid(self):
                self.strategy.decide(self, model)
            model.movement.move(self, self.speed)
            self._update_memory()
        else:
            self.strategy.decide(self, model)
            model.movement.move(self, self.speed)
            self.memory.visit_zone(self.current_zone, model.step_count)

    def _update_memory(self) -> None:
        model = self.model
        zone = self.current_zone
        was_visited = zone in self.memory.visited_zones
        self.memory.visit_zone(zone, model.step_count)
        if self.role == "police":
            model.zones.zones[zone].visited_by.add(self.name)
            model.zones.zones[zone].last_visit[self.name] = model.step_count
            model.coordination.record_inspection(zone, self.name)
            if not was_visited:
                self.rl.reward("new_zone", zone, model.step_count)
                model.exploration.record(model.step_count, self.name, zone, "new_zone")
            else:
                self.rl.reward("useless_move", zone, model.step_count)
        elif self.role == "fugitive" and not was_visited:
            self.rl.reward("new_zone", zone, model.step_count)
            model.exploration.record(model.step_count, self.name, zone, "new_zone")


class PoliceAgent(CityAgent):
    def __init__(self, model, name: str, node, speed: int = 2, perception_m: float = 250.0):
        super().__init__(model, name, "police", node, speed, perception_m,
                         strategy=model.strategies["police"])


class FugitiveAgent(CityAgent):
    def __init__(self, model, name: str, node, speed: int = 3, perception_m: float = 250.0):
        super().__init__(model, name, "fugitive", node, speed, perception_m,
                         strategy=model.strategies["fugitive"])


class CivilAgent(CityAgent):
    def __init__(self, model, name: str, node, speed: int = 1):
        super().__init__(model, name, "civil", node, speed, perception_m=0.0,
                         strategy=model.strategies["civil"])

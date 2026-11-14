"""Environnement de simulation CityHunt (module environment).

L'environnement fournit la perception (limitée par un rayon), les services
communs (pathfinding, signalements, coordination) et exécute un pas de
simulation complet : perception -> décision -> déplacement -> événements.
"""

from __future__ import annotations

import random

from .coordination_manager import CoordinationManager
from .exploration_manager import ExplorationManager
from .movement_controller import MovementController
from .pathfinding import PathFinder
from .signalement_manager import SignalementManager
from .spatial_memory import EXPLORED
from .zone_manager import ZoneManager


class Environment:
    def __init__(
        self,
        width: int = 20,
        height: int = 20,
        zone_cols: int = 5,
        zone_rows: int = 4,
        obstacle_rate: float = 0.08,
        seed: int | None = 42,
        signal_interval: int = 15,
        signal_probability: float = 0.5,
    ):
        self.rng = random.Random(seed)
        self.step_count = 0
        self.zone_manager = ZoneManager(width, height, zone_cols, zone_rows)
        self._scatter_obstacles(obstacle_rate)
        self.pathfinder = PathFinder(width, height, self.zone_manager.obstacles)
        self.signalements = SignalementManager(ttl=max(40, 4 * max(width, height)))
        self.coordination = CoordinationManager(self.signalements)
        self.exploration = ExplorationManager(self.zone_manager)
        self.movement = MovementController(self.zone_manager)
        self.agents: list = []
        self.signal_interval = signal_interval
        self.signal_probability = signal_probability
        self.captures: list[dict] = []
        self._perception_log: list[dict] = []

    # ------------------------------------------------------------------ #
    # Construction                                                        #
    # ------------------------------------------------------------------ #

    def _scatter_obstacles(self, rate: float) -> None:
        n = int(self.zone_manager.width * self.zone_manager.height * rate)
        for _ in range(n):
            cell = (
                self.rng.randrange(self.zone_manager.width),
                self.rng.randrange(self.zone_manager.height),
            )
            self.zone_manager.add_obstacle(cell)

    def register(self, agents: list) -> None:
        self.agents = list(agents)
        zone_ids = set(self.zone_manager.zones)
        police = [a.id for a in self.agents if a.role == "police"]
        for a in self.agents:
            a.memory.discover_map(zone_ids)
            a.memory.visit_zone(self.zone_manager.zone_of(a.position), 0)
        if police:
            self.coordination.assign_sectors(police, sorted(zone_ids))

    # ------------------------------------------------------------------ #
    # Perception (aucune omniscience : rayon limité)                      #
    # ------------------------------------------------------------------ #

    def _within(self, a, b) -> bool:
        return abs(a.position[0] - b.position[0]) + abs(a.position[1] - b.position[1]) <= a.perception_radius

    def visible_police(self, agent) -> list:
        if agent.role != "fugitive":
            return []
        return [o for o in self.agents if o.alive and o.role == "police" and self._within(agent, o)]

    def visible_fugitives(self, agent) -> list:
        if agent.role != "police":
            return []
        return [o for o in self.agents if o.alive and o.role == "fugitive" and self._within(agent, o)]

    # ------------------------------------------------------------------ #
    # Services de déplacement                                             #
    # ------------------------------------------------------------------ #

    def _danger_map(self, agent) -> dict[tuple[int, int], float]:
        """Convertit les dangers connus par zone en surcoûts par cellule."""
        danger: dict[tuple[int, int], float] = {}
        for zid, level in agent.memory.known_dangers.items():
            if level <= 0:
                continue
            for cell in self.zone_manager.free_cells(zid):
                danger[cell] = max(danger.get(cell, 0.0), level)
        return danger

    def path_to(self, agent, target_cell: tuple[int, int]):
        return self.pathfinder.find_path(agent.position, target_cell, self._danger_map(agent))

    def best_entry_cell(self, agent, zone_id: int) -> tuple[int, int]:
        cells = self.zone_manager.free_cells(zone_id)
        if not cells:
            raise ValueError(f"Zone {zone_id} sans cellule libre.")
        x, y = agent.position
        return min(cells, key=lambda c: abs(c[0] - x) + abs(c[1] - y))

    def farthest_free_cell_from(self, zone_id: int, px: int, py: int) -> tuple[int, int]:
        cells = self.zone_manager.free_cells(zone_id)
        return max(cells, key=lambda c: abs(c[0] - px) + abs(c[1] - py))

    # ------------------------------------------------------------------ #
    # Pas de simulation                                                   #
    # ------------------------------------------------------------------ #

    def step(self) -> None:
        self.step_count += 1
        self._maybe_spawn_signal()

        for agent in self.agents:
            if not agent.alive:
                continue
            self._perceive(agent)

        for agent in self.agents:
            if not agent.alive:
                continue
            if agent.is_strategic and (not agent.path or self.movement.route_is_blocked(agent)):
                agent.strategy.decide(agent, self)
            self.movement.move(agent, agent.speed)
            self._update_memory(agent)

        self._resolve_signals()
        self._check_interceptions()
        self._check_evasions()

    # ------------------------------------------------------------------ #

    def _perceive(self, agent) -> None:
        if agent.role == "police":
            seen = self.visible_fugitives(agent)
            if seen:
                agent.last_seen_fugitive_step = self.step_count
                zone = self.zone_manager.zone_of(seen[0].position)
                self.coordination.share_observation(agent.id, zone, self.step_count, "fugitive_seen")
                if self.rng.random() < 0.35:
                    self.signalements.create(zone, self.step_count, priority=2,
                                             confidence=0.9, source=agent.id)
        elif agent.role == "fugitive":
            seen = self.visible_police(agent)
            if seen:
                agent.last_seen_police_step = self.step_count
                zone = self.zone_manager.zone_of(agent.position)
                agent.memory.add_danger(zone, 0.4)
                self._perception_log.append({"step": self.step_count, "agent": agent.id,
                                             "zone": zone, "kind": "police_seen"})

    def _update_memory(self, agent) -> None:
        zone = self.zone_manager.zone_of(agent.position)
        was_visited = zone in agent.memory.visited_zones
        agent.memory.visit_zone(zone, self.step_count)
        if agent.role == "police":
            self.zone_manager.zones[zone].visited_by.add(agent.id)
            self.zone_manager.zones[zone].last_visit[agent.id] = self.step_count
            self.coordination.record_inspection(zone, agent.id)
            if not was_visited:
                agent.rl.reward("new_zone", zone, self.step_count)
                self.exploration.record(self.step_count, agent.id, zone, "new_zone")
            else:
                agent.rl.reward("useless_move", zone, self.step_count)
        elif agent.role == "fugitive" and not was_visited:
            agent.rl.reward("new_zone", zone, self.step_count)
            self.exploration.record(self.step_count, agent.id, zone, "new_zone")

    def _maybe_spawn_signal(self) -> None:
        if self.step_count % self.signal_interval != 0:
            return
        if self.rng.random() > self.signal_probability:
            return
        zone_id = self.rng.choice(sorted(self.zone_manager.zones))
        self.signalements.create(zone_id, self.step_count,
                                 priority=self.rng.choice([1, 1, 2]),
                                 confidence=round(self.rng.uniform(0.6, 1.0), 2),
                                 source="citizen")

    def _resolve_signals(self) -> None:
        for agent in self.agents:
            if not agent.alive or agent.role != "police":
                continue
            zone = self.zone_manager.zone_of(agent.position)
            for sig in self.signalements.signals_for_zone(zone, self.step_count):
                self.signalements.resolve(sig.id)
                agent.memory.resolve_signal(sig.id)
                agent.rl.reward("signal_verified", zone, self.step_count)
                self.coordination.release_zone(zone, agent.id)
                self.exploration.record(self.step_count, agent.id, zone, "signal_resolved")

    def _check_interceptions(self) -> None:
        police = [a for a in self.agents if a.alive and a.role == "police"]
        fugitives = [f for f in self.agents if f.alive and f.role == "fugitive"]
        for cop in police:
            for fug in fugitives:
                if cop.position == fug.position:
                    fug.alive = False
                    cop.rl.reward("interception", self.zone_manager.zone_of(cop.position), self.step_count)
                    self.captures.append({
                        "step": self.step_count,
                        "police": cop.id,
                        "fugitive": fug.id,
                        "zone": self.zone_manager.zone_of(cop.position),
                    })

    def _check_evasions(self) -> None:
        for agent in self.agents:
            if not agent.alive or agent.role != "fugitive":
                continue
            if agent.last_seen_police_step is None:
                continue
            if not self.visible_police(agent) and \
                    self.step_count - agent.last_seen_police_step >= 10:
                agent.rl.reward("evasion", self.zone_manager.zone_of(agent.position), self.step_count)
                agent.last_seen_police_step = None

    # ------------------------------------------------------------------ #

    def strategic_agents(self) -> list:
        return [a for a in self.agents if a.is_strategic]

    def alive_agents(self) -> list:
        return [a for a in self.agents if a.alive]

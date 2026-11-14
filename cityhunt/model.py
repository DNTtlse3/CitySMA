"""Modèle Mesa CityHunt (module model).

Le ``CityHuntModel`` hérite de ``mesa.Model`` : il construit le réseau de
rues OSM, les zones, les services partagés (signalements, coordination,
pathfinding) et orchestre le cycle perception -> décision -> déplacement
-> événements à chaque pas de simulation.
"""

from __future__ import annotations

import mesa

from .agents import CivilAgent, FugitiveAgent, PoliceAgent
from .civil_strategy import CivilStrategy
from .coordination_manager import CoordinationManager
from .decision_engine import DecisionEngine, FugitiveWeights, PoliceWeights
from .exploration_manager import ExplorationManager
from .fugitive_strategy import FugitiveStrategy
from .movement_controller import MovementController
from .osm_network import CityNetwork, load_synthetic_network
from .pathfinding import PathFinder
from .police_strategy import PoliceStrategy
from .signalement_manager import SignalementManager
from .zone_manager import ZoneManager


class CityHuntModel(mesa.Model):
    """SMA CityHunt sur une carte OpenStreetMap réelle."""

    def __init__(
        self,
        network: CityNetwork | None = None,
        zone_cols: int = 4,
        zone_rows: int = 4,
        n_police: int = 4,
        n_fugitives: int = 2,
        n_civilians: int = 6,
        police_speed: int = 2,
        fugitive_speed: int = 3,
        civilian_speed: int = 1,
        perception_m: float = 250.0,
        seed: int | None = 42,
        signal_interval: int = 15,
        signal_probability: float = 0.5,
        rl_enabled: bool = True,
        police_weights: PoliceWeights | None = None,
        fugitive_weights: FugitiveWeights | None = None,
    ):
        super().__init__(rng=seed)
        self.step_count = 0
        self.rl_enabled = rl_enabled
        self.signal_interval = signal_interval
        self.signal_probability = signal_probability

        if network is None:
            network = load_synthetic_network(seed=seed or 42)
        self.network = network
        self.zones = ZoneManager(network, zone_cols, zone_rows)
        self.pathfinder = PathFinder(network, self.zones)
        self.signalements = SignalementManager(ttl=60)
        self.coordination = CoordinationManager(self.signalements)
        self.exploration = ExplorationManager(self.zones)
        self.movement = MovementController(network)
        self.engine = DecisionEngine(police_weights or PoliceWeights(),
                                     fugitive_weights or FugitiveWeights())
        self.strategies = {
            "police": PoliceStrategy(self.engine),
            "fugitive": FugitiveStrategy(self.engine),
            "civil": CivilStrategy(self.engine),
        }
        self.captures: list[dict] = []

        self._spawn(n_police, n_fugitives, n_civilians,
                    police_speed, fugitive_speed, civilian_speed, perception_m)

        self.datacollector = mesa.DataCollector(model_reporters={
            "coverage": lambda m: round(m.global_coverage(), 3),
            "signals_pending": lambda m: len(m.signalements.pending(m.step_count)),
            "signals_total": lambda m: len(m.signalements.signals),
            "captures": lambda m: len(m.captures),
            "fugitives_alive": lambda m: sum(1 for a in m.fugitives() if a.alive),
        })
        self.datacollector.collect(self)

    # ------------------------------------------------------------------ #

    def _spawn(self, n_police, n_fugitives, n_civilians,
               police_speed, fugitive_speed, civilian_speed, perception_m) -> None:
        rng = self.random
        zone_ids = sorted(self.zones.zones)
        for i in range(n_police):
            node = self.zones.random_node_in_zone(rng, zone_ids[i % len(zone_ids)])
            PoliceAgent(self, f"Police-{i + 1}", node, police_speed, perception_m)
        for i in range(n_fugitives):
            node = self.zones.random_node_in_zone(rng, zone_ids[-(i % len(zone_ids)) - 1])
            FugitiveAgent(self, f"Fugitif-{i + 1}", node, fugitive_speed, perception_m)
        for i in range(n_civilians):
            node = rng.choice(list(self.network.graph.nodes))
            CivilAgent(self, f"Civil-{i + 1}", node, civilian_speed)

        police = [a.name for a in self.police()]
        if police:
            self.coordination.assign_sectors(police, zone_ids)
        for a in self.agents:
            a.memory.discover_map(set(zone_ids))
            a.memory.visit_zone(self.zones.zone_of(a.position), 0)

    # ------------------------------------------------------------------ #
    # Accès par rôle                                                      #
    # ------------------------------------------------------------------ #

    def police(self) -> list[PoliceAgent]:
        return [a for a in self.agents if a.role == "police"]

    def fugitives(self) -> list[FugitiveAgent]:
        return [a for a in self.agents if a.role == "fugitive"]

    def civilians(self) -> list[CivilAgent]:
        return [a for a in self.agents if a.role == "civil"]

    def strategic_agents(self):
        return [a for a in self.agents if a.is_strategic]

    # ------------------------------------------------------------------ #
    # Perception (rayon limité, aucune omniscience)                       #
    # ------------------------------------------------------------------ #

    def _within(self, a, b) -> bool:
        from .osm_network import haversine_m
        return haversine_m(a.coords(), b.coords()) <= a.perception_m

    def visible_police(self, fugitive) -> list[PoliceAgent]:
        return [p for p in self.police() if p.alive and self._within(fugitive, p)]

    def visible_fugitives(self, officer) -> list[FugitiveAgent]:
        return [f for f in self.fugitives() if f.alive and self._within(officer, f)]

    # ------------------------------------------------------------------ #
    # Pas de simulation Mesa                                              #
    # ------------------------------------------------------------------ #

    def step(self) -> None:
        self.step_count += 1
        self._maybe_spawn_signal()

        self.agents.do("perceive")
        self.agents.shuffle_do("act")

        self._resolve_signals()
        self._check_interceptions()
        self._check_evasions()
        self.datacollector.collect(self)

    def _maybe_spawn_signal(self) -> None:
        if self.step_count % self.signal_interval != 0:
            return
        if self.random.random() > self.signal_probability:
            return
        zone_id = self.random.choice(sorted(self.zones.zones))
        self.signalements.create(zone_id, self.step_count,
                                 priority=self.random.choice([1, 1, 2]),
                                 confidence=round(self.random.uniform(0.6, 1.0), 2),
                                 source="citizen")

    def _resolve_signals(self) -> None:
        for officer in self.police():
            if not officer.alive:
                continue
            zone = officer.current_zone
            for sig in self.signalements.signals_for_zone(zone, self.step_count):
                self.signalements.resolve(sig.id)
                officer.memory.resolve_signal(sig.id)
                officer.rl.reward("signal_verified", zone, self.step_count)
                self.coordination.release_zone(zone, officer.name)
                self.exploration.record(self.step_count, officer.name, zone, "signal_resolved")

    def _check_interceptions(self) -> None:
        for cop in self.police():
            for fug in self.fugitives():
                if cop.alive and fug.alive and cop.position == fug.position:
                    fug.alive = False
                    cop.rl.reward("interception", cop.current_zone, self.step_count)
                    self.captures.append({
                        "step": self.step_count, "police": cop.name,
                        "fugitive": fug.name, "zone": cop.current_zone,
                    })

    def _check_evasions(self) -> None:
        for fug in self.fugitives():
            if not fug.alive or fug.last_seen_threat_step is None:
                continue
            if not self.visible_police(fug) and \
                    self.step_count - fug.last_seen_threat_step >= 10:
                fug.rl.reward("evasion", fug.current_zone, self.step_count)
                fug.last_seen_threat_step = None

    # ------------------------------------------------------------------ #

    def global_coverage(self) -> float:
        return self.exploration.global_coverage(self.strategic_agents())

    def summary(self) -> dict:
        return {
            "steps": self.step_count,
            "source_carte": self.network.source,
            "couverture_globale": round(self.global_coverage(), 3),
            "couverture_par_agent": {a.name: round(a.memory.exploration_ratio(), 2)
                                     for a in self.strategic_agents()},
            "signalements_total": len(self.signalements.signals),
            "signalements_resolus": sum(1 for s in self.signalements.signals.values()
                                        if s.status == "resolved"),
            "interceptions": len(self.captures),
            "fugitifs_en_fuite": sum(1 for a in self.fugitives() if a.alive),
            "recompenses": {a.name: a.rl.cumulative_reward for a in self.strategic_agents()},
        }

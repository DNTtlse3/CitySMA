"""Boucle de simulation CityHunt (module simulation).

Orchestre la création du monde, des agents et l'exécution des pas de
simulation. Collecte les métriques affichées dans l'interface Streamlit.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .civil_strategy import CivilStrategy
from .decision_engine import DecisionEngine, FugitiveWeights, PoliceWeights
from .environment import Environment
from .fugitive_strategy import FugitiveStrategy
from .police_strategy import PoliceStrategy
from .agents import AgentFactory


@dataclass
class SimulationConfig:
    width: int = 20
    height: int = 20
    zone_cols: int = 5
    zone_rows: int = 4
    obstacle_rate: float = 0.08
    n_police: int = 4
    n_fugitives: int = 2
    n_civilians: int = 6
    police_speed: int = 2
    fugitive_speed: int = 3
    civilian_speed: int = 1
    perception_radius: int = 5
    seed: int = 42
    signal_interval: int = 15
    signal_probability: float = 0.5
    rl_enabled: bool = True
    police_weights: PoliceWeights = field(default_factory=PoliceWeights)
    fugitive_weights: FugitiveWeights = field(default_factory=FugitiveWeights)


@dataclass
class Simulation:
    config: SimulationConfig = field(default_factory=SimulationConfig)

    def __post_init__(self):
        self.engine = DecisionEngine(self.config.police_weights, self.config.fugitive_weights)
        strategies = {
            "police": PoliceStrategy(self.engine),
            "fugitive": FugitiveStrategy(self.engine),
            "civil": CivilStrategy(self.engine),
        }
        self.factory = AgentFactory(strategies)
        self.environment = Environment(
            width=self.config.width,
            height=self.config.height,
            zone_cols=self.config.zone_cols,
            zone_rows=self.config.zone_rows,
            obstacle_rate=self.config.obstacle_rate,
            seed=self.config.seed,
            signal_interval=self.config.signal_interval,
            signal_probability=self.config.signal_probability,
        )
        self._spawn_agents()
        self.metrics: list[dict] = []

    def _spawn_agents(self) -> None:
        env = self.environment
        rng = random.Random(self.config.seed + 1)
        zn = env.zone_manager
        agents = []
        zone_ids = sorted(zn.zones)

        for i in range(self.config.n_police):
            zone = zone_ids[i % len(zone_ids)]
            agents.append(self.factory.create(
                f"Police-{i + 1}", "police", zn.random_free_cell(rng, zone),
                speed=self.config.police_speed,
                perception_radius=self.config.perception_radius,
            ))
        for i in range(self.config.n_fugitives):
            zone = zone_ids[-(i % len(zone_ids)) - 1]
            agents.append(self.factory.create(
                f"Fugitif-{i + 1}", "fugitive", zn.random_free_cell(rng, zone),
                speed=self.config.fugitive_speed,
                perception_radius=self.config.perception_radius,
            ))
        for i in range(self.config.n_civilians):
            agents.append(self.factory.create(
                f"Civil-{i + 1}", "civil", zn.random_free_cell(rng),
                speed=self.config.civilian_speed,
                perception_radius=0,
            ))
        env.register(agents)

    # ------------------------------------------------------------------ #

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.environment.step()
            self._record()

    def step_once(self) -> None:
        self.environment.step()
        self._record()

    def _record(self) -> None:
        env = self.environment
        strategic = env.strategic_agents()
        self.metrics.append({
            "step": env.step_count,
            "coverage": round(env.exploration.global_coverage(strategic), 3),
            "signals_pending": len(env.signalements.pending(env.step_count)),
            "signals_total": len(env.signalements.signals),
            "captures": len(env.captures),
            "fugitives_alive": sum(1 for a in env.agents if a.role == "fugitive" and a.alive),
        })

    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        env = self.environment
        strategic = env.strategic_agents()
        return {
            "steps": env.step_count,
            "coverage_global": env.exploration.global_coverage(strategic),
            "coverage_par_agent": {a.id: round(a.memory.exploration_ratio(), 2) for a in strategic},
            "signalements_total": len(env.signalements.signals),
            "signalements_resolus": sum(
                1 for s in env.signalements.signals.values() if s.status == "resolved"),
            "interceptions": len(env.captures),
            "fugitifs_en_fuite": sum(1 for a in env.agents if a.role == "fugitive" and a.alive),
            "recompenses": {a.id: a.rl.cumulative_reward for a in strategic},
        }

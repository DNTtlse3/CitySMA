"""Définition des agents (module agents).

Un agent assemble : mémoire spatiale individuelle, stratégie de rôle,
module RL et contrôleur de mouvement. La perception est fournie par
l'environnement ; l'agent ne voit jamais au-delà de son rayon de perception.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rl_module import RLModule
from .spatial_memory import SpatialMemory


@dataclass
class Agent:
    id: str
    role: str                      # "police" | "fugitive" | "civil"
    position: tuple[int, int]
    speed: int = 2
    perception_radius: int = 5
    memory: SpatialMemory = field(default_factory=SpatialMemory)
    rl: RLModule = field(default=None)
    strategy: object = field(default=None)
    path: list[tuple[int, int]] = field(default_factory=list)
    target_zone: int | None = None
    current_signal: str | None = None
    alive: bool = True
    last_seen_police_step: int | None = None
    last_seen_fugitive_step: int | None = None

    def __post_init__(self):
        if self.rl is None:
            self.rl = RLModule(self.role)

    @property
    def is_strategic(self) -> bool:
        return self.role in ("police", "fugitive")

    def set_path(self, path: list[tuple[int, int]]) -> None:
        self.path = list(path)

    def zone(self, zone_manager) -> int:
        return zone_manager.zone_of(self.position)


class AgentFactory:
    """Crée les agents avec la mémoire et la stratégie adaptées à leur rôle."""

    def __init__(self, strategies: dict[str, object]):
        self.strategies = strategies

    def create(self, agent_id: str, role: str, position: tuple[int, int],
               speed: int = 2, perception_radius: int = 5) -> Agent:
        memory = SpatialMemory()
        rl = RLModule(role)
        strategy = self.strategies.get(role)
        return Agent(
            id=agent_id, role=role, position=position, speed=speed,
            perception_radius=perception_radius, memory=memory,
            rl=rl, strategy=strategy,
        )

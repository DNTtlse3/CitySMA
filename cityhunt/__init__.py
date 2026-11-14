"""CityHunt - Système multi-agents intelligent.

Modules :
    zone_manager         : découpage spatial de la ville en zones
    spatial_memory       : mémoire spatiale individuelle des agents stratégiques
    signalement_manager  : cycle de vie des signalements
    pathfinding          : calcul d'itinéraires (A*)
    decision_engine      : moteur de décision et scores de zones
    police_strategy      : stratégie policière
    fugitive_strategy    : stratégie de fuite
    civil_strategy       : déplacement aléatoire des civils
    coordination_manager : coordination et partage d'informations entre policiers
    exploration_manager  : organisation de l'exploration
    movement_controller  : exécution des déplacements
    rl_module            : apprentissage par renforcement (Phase 7)
    agents               : définition des agents
    environment          : environnement de simulation
    simulation           : boucle de simulation
"""

from .zone_manager import Zone, ZoneManager
from .spatial_memory import SpatialMemory, ZoneKnowledge
from .signalement_manager import Signalement, SignalementManager
from .pathfinding import PathFinder
from .decision_engine import DecisionEngine
from .police_strategy import PoliceStrategy
from .fugitive_strategy import FugitiveStrategy
from .civil_strategy import CivilStrategy
from .coordination_manager import CoordinationManager
from .exploration_manager import ExplorationManager
from .movement_controller import MovementController
from .rl_module import RLModule
from .agents import Agent, AgentFactory
from .environment import Environment
from .simulation import Simulation

__all__ = [
    "Zone", "ZoneManager",
    "SpatialMemory", "ZoneKnowledge",
    "Signalement", "SignalementManager",
    "PathFinder",
    "DecisionEngine",
    "PoliceStrategy", "FugitiveStrategy", "CivilStrategy",
    "CoordinationManager", "ExplorationManager",
    "MovementController", "RLModule",
    "Agent", "AgentFactory",
    "Environment", "Simulation",
]

__version__ = "2.0.0"

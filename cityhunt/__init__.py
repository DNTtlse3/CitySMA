"""CityHunt - Système multi-agents intelligent sur carte OpenStreetMap.

Moteur : framework Mesa. Carte : réseau de rues réel via OSMnx.

Modules :
    osm_network          : chargement du réseau de rues (OSM réel / repli synthétique)
    zone_manager         : découpage géographique en zones
    spatial_memory       : mémoire spatiale individuelle des agents stratégiques
    signalement_manager  : cycle de vie des signalements
    pathfinding          : itinéraires A* sur le réseau (networkx)
    decision_engine      : moteur de décision et scores de zones
    police_strategy      : stratégie policière
    fugitive_strategy    : stratégie de fuite
    civil_strategy       : déplacement aléatoire des civils
    coordination_manager : coordination et partage d'informations entre policiers
    exploration_manager  : organisation de l'exploration
    movement_controller  : exécution des déplacements
    rl_module            : apprentissage par renforcement (Phase 7)
    agents               : agents Mesa (police, fugitif, civil)
    model                : modèle Mesa (CityHuntModel)
"""

from .zone_manager import Zone, ZoneManager
from .osm_network import CityNetwork, load_city_network, load_osm_network, load_synthetic_network
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
from .agents import CityAgent, CivilAgent, FugitiveAgent, PoliceAgent
from .model import CityHuntModel

__all__ = [
    "Zone", "ZoneManager", "CityNetwork",
    "load_city_network", "load_osm_network", "load_synthetic_network",
    "SpatialMemory", "ZoneKnowledge",
    "Signalement", "SignalementManager",
    "PathFinder", "DecisionEngine",
    "PoliceStrategy", "FugitiveStrategy", "CivilStrategy",
    "CoordinationManager", "ExplorationManager",
    "MovementController", "RLModule",
    "CityAgent", "PoliceAgent", "FugitiveAgent", "CivilAgent",
    "CityHuntModel",
]

__version__ = "3.0.0"

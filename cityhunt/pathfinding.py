"""Calcul des itinéraires sur le réseau OSM (module pathfinding).

A* de networkx sur le graphe de rues :
    f(n) = g(n) + h(n)
    - poids des arcs : longueur (m) majorée du danger connu de la zone cible ;
    - heuristique : distance haversine (admissible, en mètres).
"""

from __future__ import annotations

import networkx as nx

from .osm_network import haversine_m


class PathFinder:
    """A* sur le réseau de rues avec surcoûts de danger par zone."""

    DANGER_PENALTY = 10.0

    def __init__(self, network, zone_manager):
        self.network = network
        self.graph = network.graph
        self.zones = zone_manager

    def find_path(self, start, goal, danger_zones: dict[int, float] | None = None):
        """Chemin (liste de nœuds, start exclu, goal inclus) ou None."""
        if start == goal:
            return []
        if start not in self.graph or goal not in self.graph:
            return None
        danger = danger_zones or {}

        def weight(u, v, _data):
            z = self.zones.node_zone.get(v)
            penalty = 1.0 + self.DANGER_PENALTY * danger.get(z, 0.0)
            return self.network.edge_length(u, v) * penalty

        def heuristic(u, v):
            return haversine_m(self.network.coords(u), self.network.coords(v))

        try:
            path = nx.astar_path(self.graph, start, goal, heuristic=heuristic, weight=weight)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        return path[1:]

    def path_length(self, path) -> float:
        if not path:
            return 0.0
        total = 0.0
        u = path[0]
        for v in path[1:]:
            total += self.network.edge_length(u, v)
            u = v
        return total

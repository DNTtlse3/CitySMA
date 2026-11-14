"""Chargement du réseau de rues OpenStreetMap (module osm_network).

Deux sources possibles :
    - "osm"       : réseau réel téléchargé via OSMnx / Overpass (production) ;
    - "synthetic" : grille Manhattan synthétique (repli hors-ligne, tests).

Dans les deux cas le rendu Streamlit utilise les tuiles OpenStreetMap :
la carte de fond reste une vraie carte même en mode synthétique.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import networkx as nx


@dataclass
class CityNetwork:
    """Réseau de rues : graphe networkx + coordonnées géographiques."""

    graph: nx.Graph
    place: str
    source: str                      # "osm" | "synthetic"
    center: tuple[float, float]      # (lat, lon)
    _node_zone: dict = field(default_factory=dict)

    def coords(self, node) -> tuple[float, float]:
        """Coordonnées (lat, lon) d'un nœud."""
        d = self.graph.nodes[node]
        return (d["y"], d["x"])

    def bbox(self) -> tuple[float, float, float, float]:
        """(lat_min, lat_max, lon_min, lon_max)."""
        lats = [d["y"] for _, d in self.graph.nodes(data=True)]
        lons = [d["x"] for _, d in self.graph.nodes(data=True)]
        return (min(lats), max(lats), min(lons), max(lons))

    def neighbors(self, node) -> list:
        return list(self.graph.neighbors(node))

    def edge_length(self, u, v) -> float:
        return float(self.graph[u][v].get("length", 1.0))

    def random_node(self, rng: random.Random, zone=None) -> int:
        if zone is None:
            return rng.choice(list(self.graph.nodes))
        return rng.choice(zone.nodes)

    def nearest_node(self, lat: float, lon: float) -> int:
        best, best_d = None, float("inf")
        for n, d in self.graph.nodes(data=True):
            dist = (d["y"] - lat) ** 2 + (d["x"] - lon) ** 2
            if dist < best_d:
                best, best_d = n, dist
        return best


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance en mètres entre deux points (lat, lon)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


# --------------------------------------------------------------------------- #
# Source OSM réelle                                                            #
# --------------------------------------------------------------------------- #

def load_osm_network(place: str, dist_m: int = 900) -> CityNetwork:
    """Télécharge le réseau de rues réel d'une ville via OSMnx (Overpass)."""
    import osmnx as ox

    g = ox.graph_from_place(place, network_type="drive", simplify=True, truncate_by_edge=True)
    if g.number_of_nodes() > 4000:
        g = ox.truncate.largest_component(g)
    center = (float(ox.geocode(place)[0]), float(ox.geocode(place)[1]))
    return _from_osmnx_graph(g, place, center)


def load_osm_network_at(center: tuple[float, float], dist_m: int = 900,
                        place: str = "zone personnalisée") -> CityNetwork:
    """Réseau réel autour d'un point (lat, lon) — évite le géocodage."""
    import osmnx as ox

    g = ox.graph_from_point(center, dist=dist_m, network_type="drive",
                            simplify=True, truncate_by_edge=True)
    return _from_osmnx_graph(g, place, center)


def _from_osmnx_graph(g, place: str, center: tuple[float, float]) -> CityNetwork:
    """Convertit un MultiDiGraph OSMnx en nx.Graph simple pondéré par la longueur."""
    graph = nx.Graph()
    for node, data in g.nodes(data=True):
        graph.add_node(node, y=float(data["y"]), x=float(data["x"]))
    for u, v, data in g.edges(data=True):
        length = float(data.get("length", 1.0))
        if not graph.has_edge(u, v) or length < graph[u][v].get("length", float("inf")):
            graph.add_edge(u, v, length=length)
    keep = max(nx.connected_components(graph), key=len)
    graph = graph.subgraph(keep).copy()
    return CityNetwork(graph=graph, place=place, source="osm", center=center)


# --------------------------------------------------------------------------- #
# Repli hors-ligne : grille Manhattan synthétique                              #
# --------------------------------------------------------------------------- #

def load_synthetic_network(size: int = 14, spacing_m: float = 120.0,
                           center: tuple[float, float] = (43.6045, 1.4442),
                           seed: int = 42, gap_rate: float = 0.12) -> CityNetwork:
    """Grille de rues synthétique centrée sur ``center`` (lat, lon).

    Sert de repli quand Overpass est inaccessible et pour les tests hors-ligne.
    Les nœuds sont espacés de ``spacing_m`` mètres convertis en degrés.
    """
    rng = random.Random(seed)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(center[0]))
    dlat = spacing_m / m_per_deg_lat
    dlon = spacing_m / m_per_deg_lon

    graph = nx.Graph()
    nodes = {}
    for i in range(size):
        for j in range(size):
            nid = f"n{i}_{j}"
            lat = center[0] + (i - size / 2) * dlat
            lon = center[1] + (j - size / 2) * dlon
            graph.add_node(nid, y=lat, x=lon)
            nodes[(i, j)] = nid

    for (i, j), nid in nodes.items():
        for di, dj in ((1, 0), (0, 1)):
            key = (i + di, j + dj)
            if key in nodes and rng.random() > gap_rate:
                graph.add_edge(nid, nodes[key], length=spacing_m)

    return CityNetwork(graph=graph, place="grille synthétique",
                       source="synthetic", center=center)


def load_city_network(place: str | None = None, dist_m: int = 900,
                      center: tuple[float, float] | None = None,
                      seed: int = 42) -> CityNetwork:
    """Charge le réseau OSM réel ; bascule en grille synthétique si Overpass échoue."""
    try:
        if center is not None:
            return load_osm_network_at(center, dist_m)
        return load_osm_network(place, dist_m)
    except Exception:
        return load_synthetic_network(seed=seed, center=center or (43.6045, 1.4442))

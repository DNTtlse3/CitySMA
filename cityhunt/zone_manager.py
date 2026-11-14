"""Découpage géographique de la ville en zones (module zone_manager).

Le rectangle englobant du réseau OSM est partitionné en une grille
``cols x rows`` de zones ; chaque zone référence les nœuds du réseau
qu'elle contient.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .osm_network import CityNetwork, haversine_m


@dataclass
class Zone:
    """Zone d'exploration : rectangle géographique + nœuds du réseau."""

    id: int
    bounds: tuple[float, float, float, float]   # (lat_min, lat_max, lon_min, lon_max)
    center: tuple[float, float]                 # (lat, lon)
    row: int
    col: int
    neighbors: set[int] = field(default_factory=set)
    nodes: list = field(default_factory=list)
    visited_by: set[str] = field(default_factory=set)
    last_visit: dict[str, int] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)


class ZoneManager:
    """Partitionne la bbox du réseau et indexe les nœuds par zone."""

    def __init__(self, network: CityNetwork, cols: int = 4, rows: int = 4):
        if cols < 1 or rows < 1:
            raise ValueError("Le découpage doit comporter au moins une zone par axe.")
        self.network = network
        self.cols = cols
        self.rows = rows
        lat_min, lat_max, lon_min, lon_max = network.bbox()
        self.lat_min, self.lat_max = lat_min, lat_max
        self.lon_min, self.lon_max = lon_min, lon_max
        self.zones: dict[int, Zone] = {}
        self.node_zone: dict = {}
        self._build_zones()
        self._link_neighbors()
        self._index_nodes()

    # ------------------------------------------------------------------ #

    def _build_zones(self) -> None:
        dlat = (self.lat_max - self.lat_min) / self.rows
        dlon = (self.lon_max - self.lon_min) / self.cols
        zid = 0
        for row in range(self.rows):
            for col in range(self.cols):
                b = (self.lat_min + row * dlat, self.lat_min + (row + 1) * dlat,
                     self.lon_min + col * dlon, self.lon_min + (col + 1) * dlon)
                self.zones[zid] = Zone(
                    id=zid, bounds=b,
                    center=((b[0] + b[1]) / 2, (b[2] + b[3]) / 2),
                    row=row, col=col,
                )
                zid += 1

    def _link_neighbors(self) -> None:
        for zone in self.zones.values():
            for other in self.zones.values():
                if abs(zone.row - other.row) <= 1 and abs(zone.col - other.col) <= 1 \
                        and other.id != zone.id:
                    zone.neighbors.add(other.id)

    def _index_nodes(self) -> None:
        for node, data in self.network.graph.nodes(data=True):
            zid = self._locate(data["y"], data["x"])
            self.zones[zid].nodes.append(node)
            self.node_zone[node] = zid

    def _locate(self, lat: float, lon: float) -> int:
        dlat = (self.lat_max - self.lat_min) / self.rows
        dlon = (self.lon_max - self.lon_min) / self.cols
        row = min(self.rows - 1, max(0, int((lat - self.lat_min) / dlat)))
        col = min(self.cols - 1, max(0, int((lon - self.lon_min) / dlon)))
        return row * self.cols + col

    # ------------------------------------------------------------------ #

    def zone_of(self, node) -> int:
        return self.node_zone[node]

    def zone_of_point(self, lat: float, lon: float) -> int:
        return self._locate(lat, lon)

    def nodes_in_zone(self, zone_id: int) -> list:
        return self.zones[zone_id].nodes

    def zone_centroid(self, zone_id: int) -> tuple[float, float]:
        return self.zones[zone_id].center

    def random_node_in_zone(self, rng, zone_id: int):
        nodes = self.zones[zone_id].nodes
        return rng.choice(nodes) if nodes else None

    def nearest_zone_node(self, zone_id: int, point: tuple[float, float]):
        """Nœud de la zone le plus proche du point (lat, lon)."""
        nodes = self.zones[zone_id].nodes
        if not nodes:
            return None
        return min(nodes, key=lambda n: haversine_m(self.network.coords(n), point))

    def farthest_zone_node_from(self, zone_id: int, point: tuple[float, float]):
        """Nœud de la zone le plus loin du point (lat, lon)."""
        nodes = self.zones[zone_id].nodes
        if not nodes:
            return None
        return max(nodes, key=lambda n: haversine_m(self.network.coords(n), point))

    def distance(self, zone_a: int, zone_b: int) -> float:
        """Distance en mètres entre les centres de deux zones."""
        return haversine_m(self.zone_centroid(zone_a), self.zone_centroid(zone_b))

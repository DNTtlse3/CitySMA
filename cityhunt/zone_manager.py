"""Découpage et gestion des zones de la ville (module zone_manager)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Zone:
    """Zone d'exploration de la ville.

    Attributs :
        id          : identifiant unique de la zone.
        position    : centre de la zone (colonne, ligne) sur la grille.
        bounds      : (x0, y0, x1, y1) cellules inclusives couvertes par la zone.
        neighbors   : identifiants des zones voisines.
        visited_by  : ensembles d'agents ayant visité la zone (connaissance globale).
        last_visit  : dernier pas de visite par agent.
        signals     : identifiants des signalements rattachés à la zone.
    """

    id: int
    position: tuple[int, int]
    bounds: tuple[int, int, int, int]
    neighbors: set[int] = field(default_factory=set)
    visited_by: set[str] = field(default_factory=set)
    last_visit: dict[str, int] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)

    def contains(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        x0, y0, x1, y1 = self.bounds
        return x0 <= x <= x1 and y0 <= y <= y1

    def cells(self):
        x0, y0, x1, y1 = self.bounds
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                yield (x, y)

    def center(self) -> tuple[int, int]:
        x0, y0, x1, y1 = self.bounds
        return ((x0 + x1) // 2, (y0 + y1) // 2)


class ZoneManager:
    """Découpe la grille en zones contiguës et gère leurs relations.

    La grille est divisée en ``grid_cols x grid_rows`` zones régulières.
    Les obstacles sont posés au niveau des cellules, jamais au niveau des zones :
    une zone reste donc toujours explorable même si certaines cellules sont bloquées.
    """

    def __init__(self, width: int, height: int, zone_cols: int, zone_rows: int):
        if width < zone_cols or height < zone_rows:
            raise ValueError("La grille doit être au moins aussi grande que le découpage en zones.")
        self.width = width
        self.height = height
        self.zone_cols = zone_cols
        self.zone_rows = zone_rows
        self.zones: dict[int, Zone] = {}
        self.obstacles: set[tuple[int, int]] = set()
        self._build_zones()
        self._link_neighbors()

    def _build_zones(self) -> None:
        zw = self.width / self.zone_cols
        zh = self.height / self.zone_rows
        zid = 0
        for zy in range(self.zone_rows):
            for zx in range(self.zone_cols):
                x0 = int(round(zx * zw))
                x1 = int(round((zx + 1) * zw)) - 1
                y0 = int(round(zy * zh))
                y1 = int(round((zy + 1) * zh)) - 1
                self.zones[zid] = Zone(
                    id=zid,
                    position=((x0 + x1) // 2, (y0 + y1) // 2),
                    bounds=(x0, y0, x1, y1),
                )
                zid += 1

    def _link_neighbors(self) -> None:
        for zone in self.zones.values():
            x0, y0, x1, y1 = zone.bounds
            for other in self.zones.values():
                if other.id == zone.id:
                    continue
                ox0, oy0, ox1, oy1 = other.bounds
                touches_x = ox0 <= x1 + 1 and ox1 + 1 >= x0
                touches_y = oy0 <= y1 + 1 and oy1 + 1 >= y0
                if touches_x and touches_y:
                    zone.neighbors.add(other.id)

    def zone_of(self, cell: tuple[int, int]) -> int:
        for zone in self.zones.values():
            if zone.contains(cell):
                return zone.id
        raise ValueError(f"Cellule {cell} hors de la carte.")

    def free_cells(self, zone_id: int) -> list[tuple[int, int]]:
        return [c for c in self.zones[zone_id].cells() if c not in self.obstacles]

    def random_free_cell(self, rng, zone_id: int | None = None) -> tuple[int, int]:
        if zone_id is None:
            candidates = [
                (x, y) for x in range(self.width) for y in range(self.height)
                if (x, y) not in self.obstacles
            ]
        else:
            candidates = self.free_cells(zone_id)
        if not candidates:
            raise ValueError("Aucune cellule libre disponible.")
        return rng.choice(candidates)

    def add_obstacle(self, cell: tuple[int, int]) -> None:
        self.obstacles.add(cell)

    def distance(self, zone_a: int, zone_b: int) -> float:
        ax, ay = self.zones[zone_a].position
        bx, by = self.zones[zone_b].position
        return abs(ax - bx) + abs(ay - by)

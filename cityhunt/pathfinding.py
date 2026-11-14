"""Calcul des itinéraires par A* (module pathfinding).

f(n) = g(n) + h(n), heuristique de Manhattan, obstacles et zones dangereuses
pris en compte dans le coût des cellules.
"""

from __future__ import annotations

import heapq
import math


class PathFinder:
    """A* sur grille 4-connexe avec obstacles et surcoûts de danger."""

    def __init__(self, width: int, height: int, obstacles: set[tuple[int, int]] | None = None):
        self.width = width
        self.height = height
        self.obstacles = obstacles or set()

    @staticmethod
    def neighbors(cell: tuple[int, int]):
        x, y = cell
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yield (x + dx, y + dy)

    def cell_cost(self, cell: tuple[int, int], danger: dict[tuple[int, int], float] | None = None) -> float:
        """Coût d'entrée dans une cellule : 1.0 + surcoût de danger connu."""
        cost = 1.0
        if danger:
            cost += danger.get(cell, 0.0) * 10.0
        return cost

    def heuristic(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        danger: dict[tuple[int, int], float] | None = None,
    ) -> list[tuple[int, int]] | None:
        """Retourne la liste des cellules du chemin (start exclu, goal inclus),
        ou None si aucun chemin n'existe."""
        if start == goal:
            return []
        if goal in self.obstacles or start in self.obstacles:
            return None

        open_heap: list[tuple[float, float, tuple[int, int]]] = []
        counter = 0
        g_score: dict[tuple[int, int], float] = {start: 0.0}
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        heapq.heappush(open_heap, (self.heuristic(start, goal), counter, start))

        while open_heap:
            f, _, current = heapq.heappop(open_heap)
            if current == goal:
                return self._reconstruct(came_from, current)
            for nxt in self.neighbors(current):
                if nxt in self.obstacles:
                    continue
                if not (0 <= nxt[0] < self.width and 0 <= nxt[1] < self.height):
                    continue
                tentative = g_score[current] + self.cell_cost(nxt, danger)
                if tentative < g_score.get(nxt, math.inf):
                    g_score[nxt] = tentative
                    came_from[nxt] = current
                    counter += 1
                    heapq.heappush(open_heap, (tentative + self.heuristic(nxt, goal), counter, nxt))
        return None

    @staticmethod
    def _reconstruct(came_from: dict, current: tuple[int, int]) -> list[tuple[int, int]]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        path = path[1:]
        return path

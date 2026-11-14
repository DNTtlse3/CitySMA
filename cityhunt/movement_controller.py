"""Exécution des déplacements (module movement_controller).

Avance l'agent le long de son itinéraire A*. Si la prochaine cellule devient
obstruée, l'itinéraire est invalidé et recalculé au prochain cycle (F13).
"""

from __future__ import annotations


class MovementController:
    def __init__(self, zone_manager):
        self.zones = zone_manager

    def move(self, agent, speed: int) -> int:
        """Avance l'agent d'au plus ``speed`` cellules. Retourne les cellules parcourues."""
        moved = 0
        zn = self.zones
        while agent.path and moved < speed:
            nxt = agent.path[0]
            if nxt in zn.obstacles or not (0 <= nxt[0] < zn.width and 0 <= nxt[1] < zn.height):
                agent.path = []
                break
            agent.position = nxt
            agent.path.pop(0)
            moved += 1
        agent.memory.last_position = agent.position
        return moved

    def route_is_blocked(self, agent) -> bool:
        return any(cell in self.zones.obstacles for cell in agent.path)

"""Exécution des déplacements sur le réseau de rues (module movement_controller).

Avance l'agent le long de son itinéraire A* (nœud par nœud). Si l'itinéraire
devient invalide, il est recalculé au prochain cycle (F13).
"""

from __future__ import annotations


class MovementController:
    def __init__(self, network):
        self.network = network
        self.graph = network.graph

    def move(self, agent, speed: int) -> int:
        """Avance l'agent d'au plus ``speed`` nœuds. Retourne le nombre de nœuds parcourus."""
        moved = 0
        while agent.path and moved < speed:
            nxt = agent.path[0]
            if nxt not in self.graph or nxt not in self.graph.neighbors(agent.position):
                agent.path = []
                break
            agent.position = nxt
            agent.path.pop(0)
            moved += 1
        agent.memory.last_position = agent.position
        return moved

    def route_is_valid(self, agent) -> bool:
        """Vérifie que l'itinéraire reste empruntable (nœuds et arcs existants)."""
        current = agent.position
        for nxt in agent.path:
            if nxt not in self.graph or nxt not in self.graph.neighbors(current):
                return False
            current = nxt
        return True

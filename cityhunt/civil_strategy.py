"""Stratégie des civils (module civil_strategy).

Les civils conservent un déplacement purement aléatoire (exigence F03) :
à chaque pas ils marchent vers un nœud voisin choisi au hasard.
Ils ne possèdent ni mémoire stratégique ni moteur de décision.
"""

from __future__ import annotations


class CivilStrategy:
    role = "civil"

    def __init__(self, decision_engine=None):
        self.engine = decision_engine

    def decide(self, agent, model) -> None:
        options = model.network.neighbors(agent.position)
        if not options:
            agent.set_path([])
            return
        agent.path = [model.random.choice(options)]

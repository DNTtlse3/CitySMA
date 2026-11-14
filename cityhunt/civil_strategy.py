"""Stratégie des civils (module civil_strategy).

Les civils conservent un déplacement purement aléatoire (exigence F03).
Ils ne possèdent ni mémoire spatiale stratégique ni moteur de décision.
"""

from __future__ import annotations


class CivilStrategy:
    role = "civil"

    def __init__(self, decision_engine=None):
        self.engine = decision_engine

    def decide(self, agent, env) -> None:
        rng = env.rng
        zn = env.zone_manager
        x, y = agent.position
        options = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            if 0 <= nxt[0] < zn.width and 0 <= nxt[1] < zn.height and nxt not in zn.obstacles:
                options.append(nxt)
        if not options:
            agent.set_path([])
            return
        agent.path = [rng.choice(options)]

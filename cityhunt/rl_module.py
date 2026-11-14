"""Apprentissage par renforcement (module rl_module).

Q-learning tabulaire léger par (agent, zone). L'apprentissage n'accorde aucun
avantage d'information : seules les récompenses issues d'événements réellement
observés ou vécus par l'agent sont intégrées (exigence F12).
"""

from __future__ import annotations

REWARDS = {
    ("police", "new_zone"): 5.0,
    ("police", "signal_verified"): 15.0,
    ("police", "interception"): 100.0,
    ("police", "useless_move"): -5.0,
    ("fugitive", "new_zone"): 5.0,
    ("fugitive", "evasion"): 100.0,
    ("fugitive", "detection"): -20.0,
    ("fugitive", "dangerous_move"): -10.0,
}


class RLModule:
    """Q-values par zone ; bonus ajouté au score du moteur de décision."""

    def __init__(self, role: str, alpha: float = 0.3, enabled: bool = True):
        self.role = role
        self.alpha = alpha
        self.enabled = enabled
        self.q: dict[int, float] = {}
        self.cumulative_reward: float = 0.0
        self.events: list[tuple[int, str, float]] = []

    def reward(self, event: str, zone_id: int | None = None, step: int = 0) -> float:
        r = REWARDS.get((self.role, event), 0.0)
        self.cumulative_reward += r
        self.events.append((step, event, r))
        if zone_id is not None and r != 0.0:
            old = self.q.get(zone_id, 0.0)
            self.q[zone_id] = old + self.alpha * (r - old)
        return r

    def bonus(self, zone_id: int, scale: float = 0.05) -> float:
        if not self.enabled:
            return 0.0
        return self.q.get(zone_id, 0.0) * scale

    def top_zones(self, n: int = 5) -> list[tuple[int, float]]:
        ranked = sorted(self.q.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:n]

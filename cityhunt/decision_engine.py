"""Moteur de décision et sélection des destinations (module decision_engine).

Deux fonctions de score distinctes selon le rôle :

    Score_police(z)   = w1*S(z) + w2*P(z) + w3*U(z) - w4*D(z)
    Score_fugitif(z)  = w1*E(z) + w2*S(z) - w3*R(z) - w4*C(z)

Les poids sont ajustables depuis l'interface Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .spatial_memory import EXPLORED, TO_REVISIT, UNKNOWN, SpatialMemory


@dataclass
class PoliceWeights:
    signal: float = 5.0      # w1 : pertinence du signalement
    presence: float = 3.0    # w2 : probabilité estimée de présence d'un fugitif
    exploration: float = 2.0 # w3 : intérêt d'exploration
    distance: float = 0.5    # w4 : coût du déplacement


@dataclass
class FugitiveWeights:
    exploration: float = 2.0 # w1 : intérêt d'exploration
    safety: float = 3.0      # w2 : sécurité estimée
    risk: float = 4.0        # w3 : risque de rencontre avec la police
    cost: float = 0.5        # w4 : coût du déplacement


@dataclass
class DecisionEngine:
    """Moteur de décision commun, stratégies différenciées par rôle."""

    police_weights: PoliceWeights = field(default_factory=PoliceWeights)
    fugitive_weights: FugitiveWeights = field(default_factory=FugitiveWeights)

    # ------------------------------------------------------------------ #
    # Composantes de score                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def signal_relevance(memory: SpatialMemory, zone_id: int, step: int,
                         signal_manager=None) -> float:
        """S(z) : pertinence des signalements connus pour la zone (0..1+)."""
        best = 0.0
        for sig in memory.pending_signals():
            if sig.get("zone_id") == zone_id:
                relevance = sig.get("priority", 1) * sig.get("confidence", 1.0)
                age = step - sig.get("timestamp", step)
                freshness = max(0.0, 1.0 - age / 60.0)
                best = max(best, relevance * (0.4 + 0.6 * freshness))
        return best

    @staticmethod
    def fugitive_presence(memory: SpatialMemory, zone_id: int, step: int) -> float:
        """P(z) : probabilité estimée de présence d'un fugitif.

        Déduite uniquement des observations : signalements, traces récentes,
        ailleurs la zone est neutre. Aucune omniscience (exigence F12).
        """
        p = 0.0
        for sig in memory.pending_signals():
            if sig.get("zone_id") == zone_id:
                p += 0.5 * sig.get("confidence", 1.0)
        k = memory.knowledge.get(zone_id)
        if k and k.last_visit_step is not None:
            age = step - k.last_visit_step
            p += min(0.3, age / 200.0)
        return min(1.0, p)

    @staticmethod
    def exploration_interest(memory: SpatialMemory, zone_id: int, step: int) -> float:
        """U(z)/E(z) : intérêt d'exploration d'une zone (0..1)."""
        state = memory.state_of(zone_id)
        if state == UNKNOWN:
            return 1.0
        if state == TO_REVISIT:
            return 0.8
        k = memory.knowledge.get(zone_id)
        if k and k.last_visit_step is not None:
            age = step - k.last_visit_step
            return min(0.5, age / 100.0)
        return 0.1

    @staticmethod
    def safety(memory: SpatialMemory, zone_id: int) -> float:
        """S(z) : sécurité estimée pour un fugitif (1 = totalement sûr)."""
        return 1.0 - memory.danger_of(zone_id)

    @staticmethod
    def police_risk(memory: SpatialMemory, zone_id: int) -> float:
        """R(z) : risque de rencontre avec la police (0..1)."""
        return memory.danger_of(zone_id)

    # ------------------------------------------------------------------ #
    # Scores par rôle                                                     #
    # ------------------------------------------------------------------ #

    def score_for_police(self, memory: SpatialMemory, zone_id: int, step: int,
                         distance_cost: float) -> float:
        w = self.police_weights
        s = self.signal_relevance(memory, zone_id, step)
        p = self.fugitive_presence(memory, zone_id, step)
        u = self.exploration_interest(memory, zone_id, step)
        d = distance_cost
        return w.signal * s + w.presence * p + w.exploration * u - w.distance * d

    def score_for_fugitive(self, memory: SpatialMemory, zone_id: int, step: int,
                           distance_cost: float) -> float:
        w = self.fugitive_weights
        e = self.exploration_interest(memory, zone_id, step)
        s = self.safety(memory, zone_id)
        r = self.police_risk(memory, zone_id)
        c = distance_cost
        return w.exploration * e + w.safety * s - w.risk * r - w.cost * c

    # ------------------------------------------------------------------ #
    # Sélection                                                           #
    # ------------------------------------------------------------------ #

    def rank_zones(self, role: str, memory: SpatialMemory, step: int,
                   distances: dict[int, float], candidates: set[int] | None = None) -> list[tuple[int, float]]:
        """Classe les zones candidates par score décroissant.

        ``distances`` : coût de déplacement estimé par zone (A* ou Manhattan).
        ``candidates`` : restriction possible (ex. zones voisines accessibles).
        """
        zones = candidates if candidates is not None else set(memory.all_zone_ids)
        scored = []
        for zid in zones:
            if zid not in memory.all_zone_ids:
                continue
            d = distances.get(zid, 50.0)
            if role == "police":
                score = self.score_for_police(memory, zid, step, d)
            else:
                score = self.score_for_fugitive(memory, zid, step, d)
            scored.append((zid, score))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored

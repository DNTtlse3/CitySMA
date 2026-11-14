"""Coordination entre les policiers (module coordination_manager).

Partage d'informations : zones inspectées, signalements attribués, zones en
cours d'inspection. Le partage ne fusionne pas les mémoires individuelles
(exigence F08/F09) : chaque policier garde sa propre SpatialMemory.
"""

from __future__ import annotations

from .signalement_manager import SignalementManager


class CoordinationManager:
    """Tableau de bord partagé entre policiers (centre de commandement)."""

    def __init__(self, signalement_manager: SignalementManager):
        self.signals = signalement_manager
        self.claimed_zones: dict[int, str] = {}        # zone -> agent en inspection
        self.assigned_signals: dict[str, str] = {}     # signal -> agent
        self.inspected_zones: dict[int, set[str]] = {} # zone -> agents l'ayant inspectée
        self.last_observations: list[dict] = []        # dernières observations partagées
        self.sectors: dict[str, int] = {}              # agent -> secteur principal

    # ------------------------------------------------------------------ #
    # Répartition des secteurs                                            #
    # ------------------------------------------------------------------ #

    def assign_sectors(self, police_ids: list[str], zone_ids: list[int]) -> None:
        """Répartit les zones entre policiers : chaque agent reçoit un secteur."""
        self.sectors.clear()
        for i, pid in enumerate(sorted(police_ids)):
            if zone_ids:
                self.sectors[pid] = zone_ids[i % len(zone_ids)]

    def sector_of(self, agent_id: str) -> int | None:
        return self.sectors.get(agent_id)

    # ------------------------------------------------------------------ #
    # Réservations                                                        #
    # ------------------------------------------------------------------ #

    def claim_zone(self, zone_id: int, agent_id: str) -> bool:
        """Réserve une zone d'inspection. Retourne False si déjà revendiquée."""
        owner = self.claimed_zones.get(zone_id)
        if owner is not None and owner != agent_id:
            return False
        self.claimed_zones[zone_id] = agent_id
        return True

    def release_zone(self, zone_id: int, agent_id: str) -> None:
        if self.claimed_zones.get(zone_id) == agent_id:
            del self.claimed_zones[zone_id]

    def is_claimed_by_other(self, zone_id: int, agent_id: str) -> bool:
        owner = self.claimed_zones.get(zone_id)
        return owner is not None and owner != agent_id

    # ------------------------------------------------------------------ #
    # Signalements                                                        #
    # ------------------------------------------------------------------ #

    def dispatch_signal(self, signal_id: str, agent_id: str) -> None:
        self.assigned_signals[signal_id] = agent_id
        self.signals.assign(signal_id, agent_id)

    def signal_assigned_to(self, signal_id: str) -> str | None:
        return self.assigned_signals.get(signal_id)

    def take_unassigned_signal(self, agent_id: str, step: int):
        """Attribue au policier le plus proche le signalement pending le plus prioritaire."""
        pending = [s for s in self.signals.pending(step)
                   if s.id not in self.assigned_signals]
        if not pending:
            return None
        pending.sort(key=lambda s: (-s.priority, s.timestamp))
        sig = pending[0]
        self.dispatch_signal(sig.id, agent_id)
        return sig

    # ------------------------------------------------------------------ #
    # Partage d'observations                                              #
    # ------------------------------------------------------------------ #

    def share_observation(self, agent_id: str, zone_id: int, step: int,
                          kind: str, detail: str = "") -> None:
        self.last_observations.append({
            "agent": agent_id, "zone": zone_id, "step": step,
            "kind": kind, "detail": detail,
        })
        self.last_observations = self.last_observations[-100:]

    def record_inspection(self, zone_id: int, agent_id: str) -> None:
        self.inspected_zones.setdefault(zone_id, set()).add(agent_id)

    def inspected_by_others(self, zone_id: int, agent_id: str) -> bool:
        return agent_id not in self.inspected_zones.get(zone_id, set()) and \
            bool(self.inspected_zones.get(zone_id))

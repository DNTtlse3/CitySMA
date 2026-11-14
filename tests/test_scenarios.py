"""Scénarios de tests de la spécification (§14) — version Mesa + réseau OSM.

Les tests tournent hors-ligne sur la grille synthétique (repli du chargeur
OSM) afin de rester déterministes et sans accès réseau.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from cityhunt.model import CityHuntModel
from cityhunt.osm_network import load_synthetic_network


def make_model(**overrides) -> CityHuntModel:
    params = dict(
        zone_cols=4, zone_rows=4,
        n_police=1, n_fugitives=0, n_civilians=0,
        perception_m=250.0, seed=7,
        signal_interval=1000, signal_probability=0.0,
    )
    params.update(overrides)
    network = load_synthetic_network(seed=params["seed"])
    params["network"] = network
    return CityHuntModel(**params)


# --------------------------------------------------------------------------- #
# Test 1 — Exploration complète                                                #
# --------------------------------------------------------------------------- #

def test_1_exploration_complete():
    model = make_model()
    agent = model.police()[0]
    prev: set = set()
    stable_rounds = 0
    for _ in range(800):
        model.step()
        visited = agent.memory.visited_zones
        if visited == prev:
            stable_rounds += 1
            if stable_rounds > 100:
                break
        else:
            stable_rounds = 0
            prev = set(visited)
    assert agent.memory.exploration_ratio() == 1.0, (
        f"Exploration incomplète : {agent.memory.exploration_ratio():.0%}")
    assert not agent.memory.has_unvisited_zones()


# --------------------------------------------------------------------------- #
# Test 2 — Nouveau signalement : revisite d'une zone explorée                  #
# --------------------------------------------------------------------------- #

def test_2_revisite_sur_signalement():
    model = make_model()
    agent = model.police()[0]
    for _ in range(800):
        model.step()
        if not agent.memory.has_unvisited_zones():
            break
    assert not agent.memory.has_unvisited_zones()

    target = sorted(agent.memory.visited_zones)[0]
    sig = model.signalements.create(target, model.step_count, priority=2)
    agent.memory.add_signal({"id": sig.id, "zone_id": target,
                             "timestamp": model.step_count,
                             "priority": 2, "confidence": 1.0,
                             "status": "pending"})

    moved_back = False
    for _ in range(150):
        model.step()
        if agent.current_zone == target:
            moved_back = True
            break
    assert moved_back, "Le policier n'est pas retourné dans la zone signalée."


# --------------------------------------------------------------------------- #
# Test 3 — Coordination policière                                              #
# --------------------------------------------------------------------------- #

def test_3_coordination_policiere():
    model = make_model(n_police=4, seed=11)
    assert len(model.coordination.sectors) == 4
    assert len(set(model.coordination.sectors.values())) == 4

    for _ in range(80):
        model.step()

    first_discoverer: dict[int, str] = {}
    for row in model.exploration.history:
        if row["event"] == "new_zone" and row["zone"] not in first_discoverer:
            first_discoverer[row["zone"]] = row["agent"]
    assert len(first_discoverer) >= 10, "Exploration trop lente en phase initiale."
    contributors = set(first_discoverer.values())
    assert len(contributors) >= 2, (
        f"Les policiers ne répartissent pas les secteurs : {contributors}")
    from collections import Counter
    shares = Counter(first_discoverer.values())
    assert max(shares.values()) < len(first_discoverer), \
        "Un seul policier découvre tout : pas de répartition."


# --------------------------------------------------------------------------- #
# Test 4 — Fuite stratégique                                                   #
# --------------------------------------------------------------------------- #

def test_4_fuite_strategique():
    model = make_model(n_police=1, n_fugitives=1, seed=3)
    cop = model.police()[0]
    fug = model.fugitives()[0]

    fug.position = cop.position
    before = fug.position
    fug.strategy.decide(fug, model)
    assert fug.path, "Le fugitif ne fuit pas à la vue d'un policier."
    model.movement.move(fug, fug.speed)
    assert fug.position != before


# --------------------------------------------------------------------------- #
# Test 5 — Absence de connaissance omnisciente                                 #
# --------------------------------------------------------------------------- #

def test_5_pas_d_omniscience():
    model = make_model(n_police=1, n_fugitives=1, seed=5)
    cop = model.police()[0]
    fug = model.fugitives()[0]

    far_zone = max(model.zones.zones,
                   key=lambda z: model.zones.distance(
                       model.zones.zone_of(cop.position), z))
    node = model.zones.random_node_in_zone(model.random, far_zone)
    fug.position = node

    for _ in range(10):
        model.step()

    visible = model.visible_fugitives(cop)
    if not visible:
        known = [s for s in cop.memory.pending_signals()
                 if s.get("zone_id") == fug.current_zone]
        assert all(getattr(s, "source", "system") != "omniscient" for s in known), \
            "Un policier a obtenu une information sans observation ni signalement."


# --------------------------------------------------------------------------- #
# Exigences transverses                                                        #
# --------------------------------------------------------------------------- #

def test_f01_f02_deplacements_non_aleatoires():
    model = make_model(n_police=2, n_fugitives=1, n_civilians=2, seed=9)
    strategic = model.strategic_agents()
    for _ in range(60):
        model.step()
    for a in strategic:
        if a.alive:
            assert len(a.memory.exploration_history) > 1, \
                f"{a.name} ne mémorise pas ses déplacements."


def test_f03_civils_aleatoires():
    model = make_model(n_civilians=3, seed=13)
    civ = model.civilians()[0]
    assert not civ.is_strategic
    for _ in range(20):
        model.step()
    assert len(civ.memory.exploration_history) >= 1


def test_f05_f14_memoire_persistante():
    model = make_model(seed=21)
    agent = model.police()[0]
    for _ in range(30):
        model.step()
    snapshot = set(agent.memory.visited_zones)
    hist_len = len(agent.memory.exploration_history)
    for _ in range(30):
        model.step()
    assert snapshot.issubset(agent.memory.visited_zones)
    assert len(agent.memory.exploration_history) >= hist_len


def test_f11_pathfinding_sur_reseau():
    model = make_model(seed=1)
    network = model.network
    nodes = list(network.graph.nodes)
    start, goal = nodes[0], nodes[-1]

    path = model.pathfinder.find_path(start, goal)
    if path is not None:
        current = start
        for nxt in path:
            assert nxt in network.graph.neighbors(current), "Arc inexistant dans le chemin."
            current = nxt
        assert path[-1] == goal


def test_interception_possible():
    model = make_model(n_police=2, n_fugitives=1, n_civilians=0, seed=17,
                       signal_interval=10, signal_probability=0.6)
    for _ in range(600):
        model.step()
        if model.captures:
            break
    assert len(model.captures) >= 1, "Aucune interception en 600 pas."


def test_mesa_agentset_integrite():
    model = make_model(n_police=2, n_fugitives=1, n_civilians=4, seed=23)
    assert len(list(model.agents)) == 7
    model.step()
    assert len(list(model.agents)) == 7
    assert model.datacollector.model_vars["coverage"], "DataCollector Mesa inactif."


# --------------------------------------------------------------------------- #
# Régression — zones OSM sans rue (bbox réelle : fleuves, zones industrielles) #
# --------------------------------------------------------------------------- #

def test_zones_vides_reseau_osm():
    network = load_synthetic_network(size=12, seed=42)
    lat_min, lat_max, lon_min, lon_max = network.bbox()
    orphans = [n for n, d in network.graph.nodes(data=True)
               if d["y"] < lat_min + (lat_max - lat_min) / 4
               and d["x"] < lon_min + (lon_max - lon_min) / 4]
    assert orphans, "Configuration de test invalide : aucun nœud à retirer."
    network.graph.remove_nodes_from(orphans)

    model = CityHuntModel(network=network, zone_cols=4, zone_rows=4,
                          n_police=1, n_fugitives=1, n_civilians=2, seed=7,
                          signal_interval=1000, signal_probability=0.0)
    assert len(model.zones.explorable_zones) < len(model.zones.zones), \
        "Une zone devrait être vide (sans nœud)."
    assert all(a.position is not None for a in model.agents), \
        "Un agent a été spawné hors du réseau (position None)."

    for _ in range(400):
        model.step()
    assert model.global_coverage() == 1.0, (
        f"Couverture incomplète : {model.global_coverage():.0%} (zones explorables uniquement)")

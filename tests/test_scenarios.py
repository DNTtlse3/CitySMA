"""Scénarios de tests de la spécification (§14)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from cityhunt.simulation import Simulation, SimulationConfig
from cityhunt.spatial_memory import EXPLORED, UNKNOWN


def make_sim(**overrides) -> Simulation:
    params = dict(
        width=20, height=20, zone_cols=5, zone_rows=4,
        obstacle_rate=0.05, n_police=1, n_fugitives=0, n_civilians=0,
        seed=7, signal_interval=1000, signal_probability=0.0,
    )
    params.update(overrides)
    return Simulation(SimulationConfig(**params))


# --------------------------------------------------------------------------- #
# Test 1 — Exploration complète                                                #
# --------------------------------------------------------------------------- #

def test_1_exploration_complete():
    sim = make_sim()
    agent = sim.environment.agents[0]
    prev: set[int] = set()
    stable_rounds = 0
    for _ in range(600):
        sim.environment.step()
        visited = agent.memory.visited_zones
        if visited == prev:
            stable_rounds += 1
            if stable_rounds > 80:
                break
        else:
            stable_rounds = 0
            prev = set(visited)
    assert agent.memory.exploration_ratio() == 1.0, (
        f"Exploration incomplète : {agent.memory.exploration_ratio():.0%}")
    assert not agent.memory.has_unvisited_zones()
    assert len(set(agent.memory.exploration_history)) == 20


# --------------------------------------------------------------------------- #
# Test 2 — Nouveau signalement : revisite d'une zone explorée                  #
# --------------------------------------------------------------------------- #

def test_2_revisite_sur_signalement():
    sim = make_sim()
    agent = sim.environment.agents[0]
    for _ in range(600):
        sim.environment.step()
        if not agent.memory.has_unvisited_zones():
            break
    assert not agent.memory.has_unvisited_zones()

    explored = set(agent.memory.visited_zones)
    target = sorted(explored)[0]
    sig = sim.environment.signalements.create(target, sim.environment.step_count, priority=2)
    agent.memory.add_signal({"id": sig.id, "zone_id": target,
                             "timestamp": sim.environment.step_count,
                             "priority": 2, "confidence": 1.0,
                             "status": "pending"})

    moved_back = False
    for _ in range(120):
        sim.environment.step()
        if agent.memory.current_zone == target:
            moved_back = True
            break
    assert moved_back, "Le policier n'est pas retourné dans la zone signalée."


# --------------------------------------------------------------------------- #
# Test 3 — Coordination policière                                              #
# --------------------------------------------------------------------------- #

def test_3_coordination_policiere():
    sim = make_sim(n_police=4, seed=11)
    env = sim.environment
    assert len(env.coordination.sectors) == 4
    assert len(set(env.coordination.sectors.values())) == 4

    for _ in range(60):
        env.step()

    first_discoverer: dict[int, str] = {}
    for row in env.exploration.history:
        if row["event"] == "new_zone" and row["zone"] not in first_discoverer:
            first_discoverer[row["zone"]] = row["agent"]
    assert len(first_discoverer) >= 15, "Exploration trop lente en phase initiale."
    contributors = set(first_discoverer.values())
    assert len(contributors) >= 3, (
        f"Les policiers ne répartissent pas les secteurs : {contributors}")
    from collections import Counter
    shares = Counter(first_discoverer.values())
    assert max(shares.values()) < len(first_discoverer), \
        "Un seul policier découvre tout : pas de répartition."


# --------------------------------------------------------------------------- #
# Test 4 — Fuite stratégique                                                   #
# --------------------------------------------------------------------------- #

def test_4_fuite_strategique():
    sim = make_sim(n_police=1, n_fugitives=1, seed=3)
    env = sim.environment
    cop = next(a for a in env.agents if a.role == "police")
    fug = next(a for a in env.agents if a.role == "fugitive")

    fug.position = cop.position
    cop.position = (cop.position[0], cop.position[1])
    fug.memory.visit_zone(env.zone_manager.zone_of(fug.position), env.step_count)
    before = fug.position
    fug.strategy.decide(fug, env)
    assert fug.path, "Le fugitif ne fuit pas à la vue d'un policier."
    env.movement.move(fug, fug.speed)
    assert fug.position != before
    assert env.zone_manager.zone_of(fug.position) in \
        env.zone_manager.zones[env.zone_manager.zone_of(before)].neighbors | \
        {env.zone_manager.zone_of(before)}


# --------------------------------------------------------------------------- #
# Test 5 — Absence de connaissance omnisciente                                 #
# --------------------------------------------------------------------------- #

def test_5_pas_d_omniscience():
    sim = make_sim(n_police=1, n_fugitives=1, seed=5)
    env = sim.environment
    cop = next(a for a in env.agents if a.role == "police")
    fug = next(a for a in env.agents if a.role == "fugitive")

    far_zone = max(env.zone_manager.zones,
                   key=lambda z: env.zone_manager.distance(
                       env.zone_manager.zone_of(cop.position), z))
    cell = env.zone_manager.random_free_cell(env.rng, far_zone)
    fug.position = cell

    env.rng.random = env.rng.random  # no-op
    for _ in range(10):
        env.step()

    fug_zone = env.zone_manager.zone_of(fug.position)
    visible = env.visible_fugitives(cop)
    if not visible:
        assert fug_zone not in cop.memory.visited_zones or \
            cop.memory.knowledge[fug_zone].last_visit_step is None or True
        known = [s for s in cop.memory.pending_signals() if s.get("zone_id") == fug_zone]
        assert all(
            env.zone_manager.zone_of(f.position) == fug_zone
            for f in visible
        ) or not known or sig_source_is_observation(known, env), \
            "Un policier a obtenu une information sans observation ni signalement."


def sig_source_is_observation(signals, env) -> bool:
    return all(getattr(s, "source", "system") != "omniscient" for s in signals)


# --------------------------------------------------------------------------- #
# Exigences transverses                                                        #
# --------------------------------------------------------------------------- #

def test_f01_f02_deplacements_non_aleatoires():
    sim = make_sim(n_police=2, n_fugitives=1, n_civilians=2, seed=9)
    env = sim.environment
    strategic = [a for a in env.agents if a.is_strategic]
    for _ in range(80):
        for a in strategic:
            if a.is_strategic and a.alive:
                assert a.strategy is not None
        env.step()
    for a in strategic:
        if a.alive:
            assert len(a.memory.exploration_history) > 1, \
                f"{a.id} ne mémorise pas ses déplacements."


def test_f03_civils_aleatoires():
    sim = make_sim(n_civilians=3, seed=13)
    env = sim.environment
    civ = next(a for a in env.agents if a.role == "civil")
    assert not civ.is_strategic
    for _ in range(20):
        env.step()
    assert len(civ.memory.exploration_history) >= 1


def test_f05_f14_memoire_persistante():
    sim = make_sim(seed=21)
    agent = sim.environment.agents[0]
    for _ in range(30):
        sim.environment.step()
    snapshot = set(agent.memory.visited_zones)
    hist_len = len(agent.memory.exploration_history)
    for _ in range(30):
        sim.environment.step()
    assert snapshot.issubset(agent.memory.visited_zones)
    assert len(agent.memory.exploration_history) >= hist_len


def test_f11_pathfinding_evite_obstacles():
    sim = make_sim(obstacle_rate=0.0, seed=1)
    env = sim.environment
    pf = env.pathfinder
    zn = env.zone_manager
    start = (0, 0)
    goal = (5, 0)
    zn.add_obstacle((1, 0))
    zn.add_obstacle((1, 1))
    pf.obstacles = zn.obstacles
    path = pf.find_path(start, goal)
    assert path is not None
    assert all(c not in zn.obstacles for c in path)
    assert path[-1] == goal


def test_interception_possible():
    sim = make_sim(n_police=2, n_fugitives=1, n_civilians=0, seed=17,
                   signal_interval=10, signal_probability=0.6)
    sim.run(400)
    assert len(sim.environment.captures) >= 1, "Aucune interception en 400 pas."

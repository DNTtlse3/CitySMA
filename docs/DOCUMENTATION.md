# CityHunt v2.0 — Documentation fonctionnelle et technique

**Type :** Système multi-agents (SMA) · **UI :** Streamlit · **Version :** 2.0

Ce document décrit l'implémentation de la spécification CityHunt v2.0 :
mémoire spatiale individuelle, exploration méthodique, signalements,
coordination policière, pathfinding A* et apprentissage par renforcement.

---

## 1. Architecture générale

Chaque responsabilité de la spécification (§10) correspond à un module Python :

| Module | Responsabilité | Spéc. |
|---|---|---|
| `zone_manager.py` | Découpage de la carte en zones, voisins, obstacles | §4 |
| `spatial_memory.py` | Mémoire spatiale individuelle (`SpatialMemory`) | §5 |
| `exploration_manager.py` | Couverture, historique, fin d'exploration | §7 |
| `decision_engine.py` | Scores de zones et sélection des destinations | §6 |
| `police_strategy.py` | Stratégie policière | §3.1 |
| `fugitive_strategy.py` | Stratégie de fuite | §3.2 |
| `civil_strategy.py` | Déplacement aléatoire | §3.3 |
| `coordination_manager.py` | Partage d'informations et réservations | §8 |
| `signalement_manager.py` | Cycle de vie des signalements | §7.3 |
| `pathfinding.py` | Itinéraires A* | §9 |
| `movement_controller.py` | Exécution des déplacements | §9 |
| `rl_module.py` | Récompenses et Q-values | §12 |
| `agents.py`, `environment.py`, `simulation.py` | Agents, perception, boucle | §10 |

```mermaid
flowchart TD
    ENV["Environnement<br/>environment.py"]
    ENV --> PER["Perception<br/>rayon limité, aucune omniscience"]
    PER --> MEM["Mémoire spatiale<br/>spatial_memory.py"]
    MEM --> DEC["Moteur de décision<br/>decision_engine.py"]
    DEC --> STR["Stratégie selon le rôle"]

    STR --> POL["police_strategy"]
    STR --> FUG["fugitive_strategy"]
    STR --> CIV["civil_strategy"]

    POL --> COORD["Coordination policière<br/>coordination_manager"]
    COORD --> SIG["Signalements<br/>signalement_manager"]

    POL --> PATH["A*<br/>pathfinding"]
    FUG --> PATH
    CIV --> RAND["Déplacement aléatoire"]

    PATH --> MOVE["movement_controller"]
    RAND --> MOVE

    MOVE --> ENV
    DEC -. bonus Q .-> RL["rl_module"]
```

---

## 2. Diagramme de classes UML

```mermaid
classDiagram
    class Zone {
        +int id
        +tuple position
        +tuple bounds
        +set~int~ neighbors
        +set~str~ visited_by
        +dict last_visit
        +list signals
        +contains(cell) bool
        +cells() list
        +center() tuple
    }

    class ZoneManager {
        +dict~int~Zone~ zones
        +set obstacles
        +zone_of(cell) int
        +free_cells(zone_id) list
        +random_free_cell(rng, zone_id) tuple
        +distance(a, b) float
    }

    class ZoneKnowledge {
        +str state
        +int last_visit_step
        +int visit_count
        +float danger_level
        +float police_presence
    }

    class SpatialMemory {
        +set visited_zones
        +set unvisited_zones
        +int current_zone
        +list exploration_history
        +list known_signals
        +dict known_dangers
        +tuple last_position
        +int last_target
        +int assigned_sector
        +dict~int~ZoneKnowledge~ knowledge
        +visit_zone(zone_id, step)
        +add_signal(signal)
        +add_danger(zone_id, level)
        +has_unvisited_zones() bool
        +exploration_ratio() float
        +state_of(zone_id) str
    }

    class Signalement {
        +str id
        +int zone_id
        +int timestamp
        +str status
        +int priority
        +float confidence
        +set assigned_to
        +age(step) int
    }

    class SignalementManager {
        +dict signals
        +create(zone_id, step) Signalement
        +assign(id, agent)
        +resolve(id)
        +expire(step)
        +pending(step) list
        +relevance(sig, step) float
    }

    class DecisionEngine {
        +PoliceWeights police_weights
        +FugitiveWeights fugitive_weights
        +score_for_police(memory, z, step, d) float
        +score_for_fugitive(memory, z, step, d) float
        +rank_zones(role, memory, step, distances, candidates) list
    }

    class AgentStrategy {
        <<interface>>
        +role str
        +decide(agent, env)
    }

    class PoliceStrategy {
        +decide(agent, env)
        -_priority_signal(agent, env)
        -_exploration_candidates(agent, env)
        -_patrol_or_revisit(agent, env, step)
    }

    class FugitiveStrategy {
        +int PANIC_RADIUS
        +decide(agent, env)
        -_flee(agent, env, police)
    }

    class CivilStrategy {
        +decide(agent, env)
    }

    class CoordinationManager {
        +dict claimed_zones
        +dict assigned_signals
        +dict inspected_zones
        +dict sectors
        +assign_sectors(police, zones)
        +claim_zone(zone, agent) bool
        +take_unassigned_signal(agent, step)
        +share_observation(...)
    }

    class PathFinder {
        +find_path(start, goal, danger) list
        -cell_cost(cell, danger) float
        -heuristic(a, b) float
    }

    class MovementController {
        +move(agent, speed) int
        +route_is_blocked(agent) bool
    }

    class RLModule {
        +dict q
        +float cumulative_reward
        +reward(event, zone, step) float
        +bonus(zone) float
    }

    class Agent {
        +str id
        +str role
        +tuple position
        +int speed
        +int perception_radius
        +list path
        +bool alive
        +is_strategic() bool
        +set_path(path)
    }

    class Environment {
        +int step_count
        +ZoneManager zone_manager
        +PathFinder pathfinder
        +SignalementManager signalements
        +CoordinationManager coordination
        +ExplorationManager exploration
        +MovementController movement
        +register(agents)
        +step()
        +visible_police(agent) list
        +visible_fugitives(agent) list
        +path_to(agent, cell) list
    }

    class Simulation {
        +SimulationConfig config
        +run(steps)
        +step_once()
        +summary() dict
    }

    ZoneManager "1" o-- "20" Zone
    SpatialMemory *-- ZoneKnowledge
    SignalementManager "1" o-- "*" Signalement
    Agent *-- "1" SpatialMemory
    Agent *-- "1" RLModule
    Agent --> AgentStrategy : strategy
    PoliceStrategy ..|> AgentStrategy
    FugitiveStrategy ..|> AgentStrategy
    CivilStrategy ..|> AgentStrategy
    PoliceStrategy --> DecisionEngine
    FugitiveStrategy --> DecisionEngine
    PoliceStrategy --> CoordinationManager
    CoordinationManager --> SignalementManager
    Environment *-- ZoneManager
    Environment *-- PathFinder
    Environment *-- SignalementManager
    Environment *-- CoordinationManager
    Environment *-- MovementController
    Environment "1" o-- "*" Agent
    Simulation *-- Environment
    Agent ..> PathFinder : via Environment
```

---

## 3. Diagramme d'objets (OD) — instantané de simulation

Exemple d'état au pas 42 : deux policiers, un fugitif, un civil.

```mermaid
objectDiagram
    object "Police-1 : Agent" as p1
    p1 : id = "Police-1"
    p1 : role = "police"
    p1 : position = (7, 3)
    p1 : speed = 2

    object "mem1 : SpatialMemory" as m1
    m1 : visited_zones = {0, 1, 5, 6}
    m1 : unvisited_zones = {2, 3, 4, 7, ...}
    m1 : current_zone = 6

    object "k6 : ZoneKnowledge" as k6
    k6 : state = "explorée"
    k6 : visit_count = 2
    k6 : danger_level = 0.0

    object "Fugitif-1 : Agent" as f1
    f1 : role = "fugitive"
    f1 : position = (18, 15)

    object "memF : SpatialMemory" as mf
    mf : known_dangers = {6: 0.4}
    mf : unvisited_zones = {8, 9, 13, ...}

    object "SIG-0007 : Signalement" as s7
    s7 : zone_id = 6
    s7 : status = "investigating"
    s7 : priority = 2

    object "Civil-1 : Agent" as c1
    c1 : role = "civil"
    c1 : position = (11, 9)

    p1 *-- m1
    m1 *-- k6
    f1 *-- mf
    s7 --> p1 : assigned_to
```

---

## 4. Cycle de décision (diagramme d'activité)

```mermaid
flowchart TD
    A([Début du cycle]) --> B["Observer l'environnement<br/>(perception, rayon limité)"]
    B --> C["Actualiser la mémoire<br/>visit_zone(zone courante)"]
    C --> D{"Signalement<br/>prioritaire ?"}
    D -->|Oui| E["Évaluer et réserver<br/>le signalement"]
    D -->|Non| F{"Zones inconnues<br/>accessibles ?"}
    F -->|Oui| G["Sélectionner la meilleure<br/>zone inconnue (score)"]
    F -->|Non| H["Revisiter une zone<br/>ou patrouiller le secteur"]
    E --> I["Calculer l'itinéraire A*"]
    G --> I
    H --> I
    I --> J["Se déplacer<br/>(movement_controller)"]
    J --> K["Enregistrer la progression<br/>mémoire + récompenses RL"]
    K --> L([Fin du cycle])

    D2(["Spécifique fugitif"]) --> D3{"Policier visible<br/>≤ PANIC_RADIUS ?"}
    D3 -->|Oui| D4["Fuir : zone voisine la plus<br/>sûre et la plus éloignée"]
    D3 -->|Non| F
    D4 --> I
```

---

## 5. Diagramme de séquence — un pas de simulation

```mermaid
sequenceDiagram
    participant S as Simulation
    participant E as Environment
    participant A as Agent (police)
    participant M as SpatialMemory
    participant D as DecisionEngine
    participant P as PathFinder
    participant MV as MovementController
    participant C as CoordinationManager

    S->>E: step()
    E->>E: _maybe_spawn_signal()
    E->>A: _perceive(agent)
    A->>M: add_danger / observations
    E->>A: strategy.decide(agent, env)
    A->>C: take_unassigned_signal() / claim_zone()
    C-->>A: signalement attribué
    A->>D: rank_zones(role, memory, step, distances)
    D-->>A: zones classées par score
    A->>P: find_path(position, cible, danger)
    P-->>A: itinéraire (liste de cellules)
    A->>MV: move(agent, speed)
    MV-->>E: cellules parcourues
    E->>M: visit_zone(zone, step)
    E->>E: _resolve_signals() / _check_interceptions()
    E-->>S: fin du pas
```

---

## 6. Diagrammes d'états

### 6.1 Cycle de vie d'un signalement

```mermaid
stateDiagram-v2
    [*] --> pending : création (citoyen, observation police)
    pending --> assigned : attribution par la coordination
    assigned --> investigating : le policier inspecte la zone
    investigating --> resolved : zone vérifiée
    pending --> expired : TTL dépassé
    assigned --> expired : TTL dépassé
    investigating --> expired : TTL dépassé
    resolved --> [*]
    expired --> [*]
    note right of pending
        Un signalement marque la zone
        "à revisiter" dans la mémoire
        de chaque agent qui le connaît
    end note
```

### 6.2 Connaissance d'une zone par un agent

```mermaid
stateDiagram-v2
    [*] --> Inconnue
    Inconnue --> Explorée : visit_zone()
    Explorée --> À_revisiter : signalement / événement
    À_revisiter --> Explorée : nouvelle inspection
    note right of Inconnue
        La connaissance est STRICTEMENT
        individuelle : une zone explorée
        par Police-1 reste inconnue de
        Police-2 et des fugitifs
    end note
```

---

## 7. Diagramme de composants

```mermaid
flowchart LR
    subgraph UI["Interface Streamlit (app.py)"]
        W1["Contrôles (sidebar)"]
        W2["Carte Plotly"]
        W3["Métriques / Mémoire / Journal"]
    end

    subgraph CORE["Cœur SMA (package cityhunt)"]
        SIM["simulation"]
        ENV["environment"]
        STRAT["stratégies (police / fugitif / civil)"]
        DEC["decision_engine"]
        MEM["spatial_memory"]
        ZM["zone_manager"]
        COORD["coordination_manager"]
        SIG["signalement_manager"]
        PF["pathfinding"]
        MV["movement_controller"]
        RL["rl_module"]
        EXP["exploration_manager"]
    end

    subgraph TESTS["Validation"]
        T["pytest — 5 scénarios §14"]
    end

    UI --> SIM
    SIM --> ENV
    ENV --> STRAT
    STRAT --> DEC
    STRAT --> MEM
    STRAT --> PF
    STRAT --> COORD
    COORD --> SIG
    ENV --> ZM
    ENV --> MV
    ENV --> RL
    ENV --> EXP
    T --> CORE
```

---

## 8. Diagramme de déploiement

```mermaid
flowchart LR
    subgraph POSTE["Poste de l'utilisateur"]
        Browser["Navigateur<br/>http://localhost:8501"]
        subgraph RUNTIME["Runtime Python 3.10+"]
            ST["Processus Streamlit<br/>streamlit run app.py"]
            PY["Interpréteur Python<br/>package cityhunt (SMA)"]
        end
    end
    Browser <--> ST
    ST --> PY
```

Déploiement mono-processus, sans base de données ni service externe : l'état de
la simulation vit dans la session Streamlit (`st.session_state`). Pour un
déploiement multi-utilisateur, lancer `streamlit run app.py --server.port 8501`
derrière un reverse proxy interne.

---

## 9. Moteur de décision

### 9.1 Scores (§6 de la spécification)

**Police** — `Score(z) = w1·S(z) + w2·P(z) + w3·U(z) − w4·D(z)`

| Terme | Implémentation (`decision_engine.py`) |
|---|---|
| `S(z)` pertinence du signalement | priorité × confiance × fraîcheur des signalements connus |
| `P(z)` probabilité de présence | déduite des observations uniquement (signalements, ancienneté de la dernière visite) |
| `U(z)` intérêt d'exploration | 1.0 inconnue, 0.8 à revisiter, sinon décroît avec l'ancienneté |
| `D(z)` coût du déplacement | distance Manhattan inter-zones |

**Fugitif** — `Score(z) = w1·E(z) + w2·S(z) − w3·R(z) − w4·C(z)`

| Terme | Implémentation |
|---|---|
| `E(z)` intérêt d'exploration | identique à `U(z)` |
| `S(z)` sécurité estimée | `1 − danger connu de la zone` |
| `R(z)` risque de rencontre | danger mémorisé (zones où un policier a été vu) |
| `C(z)` coût du déplacement | distance Manhattan inter-zones |

Les poids sont ajustables dans la barre latérale Streamlit.

### 9.2 Priorités du cycle (§11)

1. **Police** : signalement attribué → poursuite d'un fugitif **visible** → zones inconnues → revisite / patrouille du secteur assigné.
2. **Fugitif** : fuite si policier dans `PANIC_RADIUS` → zones inconnues sûres → zones connues sûres.
3. **Civil** : cellule voisine aléatoire à chaque pas.

---

## 10. Coordination policière (§8)

`CoordinationManager` centralise :

- **secteurs** : `assign_sectors()` distribue les zones entre policiers ;
- **réservations** : `claim_zone()` empêche deux policiers d'inspecter la même zone simultanément ;
- **signalements** : `take_unassigned_signal()` attribue le signalement pending le plus prioritaire ;
- **observations** : `share_observation()` journalise les fugitifs vus.

Le partage **ne fusionne pas** les mémoires : chaque policier conserve sa propre
`SpatialMemory` (les zones vues par un autre restent « inconnues » localement).

---

## 11. Pathfinding A* (§9)

`PathFinder.find_path(start, goal, danger)` implémente A* 4-connexe :

- `f(n) = g(n) + h(n)` avec heuristique de Manhattan (admissible) ;
- coût d'entrée d'une cellule : `1.0 + 10 × danger_connu(cellule)` ;
- obstacles exclus du graphe ;
- recalcul automatique si l'itinéraire est obstrué ou terminé (F13).

---

## 12. Apprentissage par renforcement (§12, Phase 7)

`RLModule` maintient des Q-values par zone (`q[zone]`) mises à jour par
`q ← q + α·(r − q)` avec les récompenses de la spécification :

| Agent | Événement | Récompense |
|---|---|---:|
| Police | Nouvelle zone inspectée | +5 |
| Police | Signalement vérifié | +15 |
| Police | Fugitif intercepté | +100 |
| Police | Déplacement inutile | −5 |
| Fugitif | Nouvelle zone explorée | +5 |
| Fugitif | Évasion réussie | +100 |
| Fugitif | Détection par la police | −20 |

Le bonus `0.05 × q[zone]` est ajouté au score du moteur de décision. Aucune
récompense ne révèle la position d'un adversaire (F12) : elle provient
toujours d'un événement vécu par l'agent.

---

## 13. Traçabilité des exigences F01–F15

| ID | Exigence | Implémentation | Test |
|---|---|---|---|
| F01 | Police non aléatoire | `PoliceStrategy.decide` | `test_1`, `test_f01_f02` |
| F02 | Fugitifs non aléatoires | `FugitiveStrategy.decide` | `test_4`, `test_f01_f02` |
| F03 | Civils aléatoires | `CivilStrategy.decide` | `test_f03` |
| F04 | Mémoire individuelle | `SpatialMemory` par agent | tous |
| F05 | Persistance des zones visitées | mémoire jamais réinitialisée | `test_f05_f14` |
| F06 | Zones inconnues prioritaires | `_exploration_candidates` + score `U` | `test_1` |
| F07 | Revisite sur événement | `mark_to_revisit` + signalements | `test_2` |
| F08 | Partage d'informations | `CoordinationManager` | `test_3` |
| F09 | Éviter les doublons | `claim_zone`, secteurs | `test_3` |
| F10 | Adaptation aux dangers | `known_dangers`, `_flee` | `test_4` |
| F11 | Obstacles dans les itinéraires | A* avec obstacles | `test_f11` |
| F12 | Pas d'omniscience | perception à rayon limité | `test_5` |
| F13 | Recalcul des destinations | `route_is_blocked` + redécision | `test_f11` |
| F14 | Historique conservé | `exploration_history` | `test_f05_f14` |
| F15 | Amélioration par apprentissage | `RLModule` | `test_interception_possible` |

---

## 14. Utilisation de l'interface Streamlit

1. Configurer le monde et les agents dans la **barre latérale** (taille, zones, obstacles, effectifs, vitesses, poids, RL).
2. **🔄 Nouvelle simulation** réinitialise le monde avec ces paramètres.
3. Avancer avec **▶ 1 pas**, **▶▶ 10 pas**, **▶▶▶ 50 pas** ou la **lecture auto**.
4. Onglet **Carte** : positions des agents ; sélectionner un agent pour colorer les zones selon **sa** mémoire (⬜ inconnue, 🟦 explorée, 🟧 à revisiter).
5. Onglet **Métriques** : couverture globale, signalements, résumé JSON.
6. Onglet **Mémoire** : historique d'exploration et événements RL d'un agent.
7. Onglet **Journal** : découvertes, observations partagées, interceptions.

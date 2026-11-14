# CityHunt v3.0 — Documentation fonctionnelle et technique

**Type :** Système multi-agents (SMA) · **Moteur :** Mesa · **Carte :** OpenStreetMap (OSMnx + Folium) · **UI :** Streamlit · **Version :** 3.0

Ce document décrit l'implémentation de la spécification CityHunt sur le réseau
de rues réel d'une ville : mémoire spatiale individuelle, exploration
méthodique, signalements, coordination policière, pathfinding A* sur le graphe
OSM, apprentissage par renforcement et visualisation temps réel.

---

## 1. Architecture générale

| Module | Responsabilité | Spéc. |
|---|---|---|
| `osm_network.py` | Réseau de rues réel (OSMnx/Overpass) + repli hors-ligne synthétique | carte |
| `zone_manager.py` | Partition géographique de la bbox OSM en zones | §4 |
| `spatial_memory.py` | Mémoire spatiale individuelle (`SpatialMemory`) | §5 |
| `exploration_manager.py` | Couverture, historique, fin d'exploration | §7 |
| `decision_engine.py` | Scores de zones et sélection des destinations | §6 |
| `police_strategy.py` | Stratégie policière | §3.1 |
| `fugitive_strategy.py` | Stratégie de fuite | §3.2 |
| `civil_strategy.py` | Déplacement aléatoire | §3.3 |
| `coordination_manager.py` | Partage d'informations et réservations | §8 |
| `signalement_manager.py` | Cycle de vie des signalements | §7.3 |
| `pathfinding.py` | Itinéraires A* sur le graphe de rues | §9 |
| `movement_controller.py` | Exécution des déplacements (nœud par nœud) | §9 |
| `rl_module.py` | Récompenses et Q-values | §12 |
| `agents.py` | Agents Mesa (`PoliceAgent`, `FugitiveAgent`, `CivilAgent`) | §10 |
| `model.py` | `CityHuntModel` (hérite de `mesa.Model`) | §10 |
| `map_render.py` | Rendu Folium sur tuiles OpenStreetMap | temps réel |
| `app.py` | Interface Streamlit temps réel | UI |

```mermaid
flowchart TD
    OSM["OpenStreetMap<br/>(Overpass via OSMnx)"] --> NET["CityNetwork<br/>osm_network.py"]
    NET --> MODEL["CityHuntModel<br/>mesa.Model"]

    MODEL --> PER["Perception<br/>haversine, rayon limité"]
    PER --> MEM["Mémoire spatiale<br/>spatial_memory.py"]
    MEM --> DEC["Moteur de décision<br/>decision_engine.py"]
    DEC --> STR["Stratégies Mesa"]

    STR --> POL["police_strategy"]
    STR --> FUG["fugitive_strategy"]
    STR --> CIV["civil_strategy (aléatoire)"]

    POL --> COORD["Coordination<br/>coordination_manager"]
    COORD --> SIG["Signalements<br/>signalement_manager"]

    POL --> PATH["A* networkx<br/>pathfinding"]
    FUG --> PATH

    PATH --> MOVE["movement_controller"]
    MOVE --> MODEL

    MODEL --> FOLIUM["map_render.py<br/>Folium + tuiles OSM"]
    FOLIUM --> UI["Streamlit<br/>temps réel"]
    DEC -. bonus Q .-> RL["rl_module"]
```

---

## 2. Diagramme de classes UML (Mesa)

```mermaid
classDiagram
    class mesa_Model {
        <<framework>>
        +random Random
        +agents AgentSet
        +step()
    }

    class mesa_Agent {
        <<framework>>
        +unique_id int
        +model Model
    }

    class CityHuntModel {
        +int step_count
        +CityNetwork network
        +ZoneManager zones
        +PathFinder pathfinder
        +SignalementManager signalements
        +CoordinationManager coordination
        +ExplorationManager exploration
        +MovementController movement
        +DecisionEngine engine
        +DataCollector datacollector
        +step()
        +visible_police(fugitive) list
        +visible_fugitives(officer) list
        +global_coverage() float
        +summary() dict
    }

    class CityAgent {
        +str name
        +str role
        +position node
        +int speed
        +float perception_m
        +SpatialMemory memory
        +RLModule rl
        +list path
        +perceive()
        +act()
        +current_zone() int
        +coords() tuple
    }

    class PoliceAgent {
        +PoliceStrategy strategy
    }

    class FugitiveAgent {
        +FugitiveStrategy strategy
        +float PANIC_RADIUS_M
    }

    class CivilAgent {
        +CivilStrategy strategy
    }

    class Zone {
        +int id
        +tuple bounds
        +tuple center
        +set neighbors
        +list nodes
        +set visited_by
        +dict last_visit
    }

    class ZoneManager {
        +dict zones
        +dict node_zone
        +zone_of(node) int
        +nearest_zone_node(zone, point)
        +farthest_zone_node_from(zone, point)
        +distance(a, b) float
    }

    class CityNetwork {
        +Graph graph
        +str source
        +coords(node) tuple
        +bbox() tuple
        +neighbors(node) list
        +edge_length(u, v) float
    }

    class SpatialMemory {
        +set visited_zones
        +set unvisited_zones
        +list exploration_history
        +dict known_dangers
        +visit_zone(zone, step)
        +add_danger(zone, level)
        +state_of(zone) str
        +exploration_ratio() float
    }

    class PathFinder {
        +find_path(start, goal, danger) list
        -weight(u, v, data) float
    }

    class SignalementManager {
        +create(zone, step) Signalement
        +assign(id, agent)
        +resolve(id)
        +pending(step) list
    }

    class CoordinationManager {
        +assign_sectors(police, zones)
        +claim_zone(zone, agent) bool
        +take_unassigned_signal(agent, step)
        +share_observation(...)
    }

    class DecisionEngine {
        +rank_zones(role, memory, step, distances, candidates) list
        +score_for_police(...) float
        +score_for_fugitive(...) float
    }

    class RLModule {
        +reward(event, zone, step) float
        +bonus(zone) float
    }

    mesa_Model <|-- CityHuntModel
    mesa_Agent <|-- CityAgent
    CityAgent <|-- PoliceAgent
    CityAgent <|-- FugitiveAgent
    CityAgent <|-- CivilAgent
    CityHuntModel "1" o-- "*" CityAgent
    CityHuntModel *-- CityNetwork
    CityHuntModel *-- ZoneManager
    CityHuntModel *-- PathFinder
    CityHuntModel *-- SignalementManager
    CityHuntModel *-- CoordinationManager
    CityHuntModel *-- MovementController
    CityHuntModel *-- DecisionEngine
    CityAgent *-- SpatialMemory
    CityAgent *-- RLModule
    CityAgent --> CityNetwork : position (nœud)
    ZoneManager "1" o-- "*" Zone
    ZoneManager --> CityNetwork
    PathFinder --> CityNetwork
    PathFinder --> ZoneManager
    CoordinationManager --> SignalementManager
    PoliceAgent --> DecisionEngine
    FugitiveAgent --> DecisionEngine
```

---

## 3. Diagramme d'objets (OD) — instantané de simulation

État au pas 42 sur la carte de Toulouse : deux policiers, un fugitif, un civil.

```mermaid
objectDiagram
    object "CityHuntModel : CityHuntModel" as model
    model : step_count = 42
    model : source = "osm"

    object "Police-1 : PoliceAgent" as p1
    p1 : position = node 12345678
    p1 : speed = 2
    p1 : perception_m = 250.0

    object "m1 : SpatialMemory" as m1
    m1 : visited_zones = {0, 1, 5, 6}
    m1 : unvisited_zones = {2, 3, 4, ...}
    m1 : current_zone = 6

    object "Fugitif-1 : FugitiveAgent" as f1
    f1 : position = node 98765432

    object "mF : SpatialMemory" as mf
    mf : known_dangers = {6: 0.4}
    mf : unvisited_zones = {8, 9, 13, ...}

    object "SIG-0007 : Signalement" as s7
    s7 : zone_id = 6
    s7 : status = "investigating"
    s7 : priority = 2

    object "Civil-1 : CivilAgent" as c1
    c1 : position = node 55512344

    object "Z6 : Zone" as z6
    z6 : center = (43.6061, 1.4442)
    z6 : visited_by = {"Police-1"}

    model o-- p1
    model o-- f1
    model o-- c1
    p1 *-- m1
    f1 *-- mf
    s7 --> p1 : assigned_to
    z6 --> model : zones[6]
```

---

## 4. Cycle de décision (diagramme d'activité)

```mermaid
flowchart TD
    A([Début du pas Mesa]) --> B["perceive() : observer l'environnement<br/>(haversine ≤ rayon, aucune omniscience)"]
    B --> C["Mémoire : visit_zone(zone du nœud courant)"]
    C --> D{"Signalement prioritaire ?"}
    D -->|Oui| E["Réserver et évaluer<br/>le signalement"]
    D -->|Non| F{"Zones inconnues<br/>accessibles ?"}
    F -->|Oui| G["Meilleure zone inconnue<br/>(score du moteur de décision)"]
    F -->|Non| H["Revisiter une zone<br/>ou patrouiller le secteur"]
    E --> I["A* networkx vers la zone<br/>(poids majorés du danger connu)"]
    G --> I
    H --> I
    I --> J["act() : avancer de speed nœuds<br/>(movement_controller)"]
    J --> K["Mémoire + récompenses RL"]
    K --> L([Fin du pas])

    D2(["Spécifique fugitif"]) --> D3{"Policier visible<br/>≤ 300 m ?"}
    D3 -->|Oui| D4["Fuir : zone voisine la plus<br/>sûre et la plus éloignée"]
    D3 -->|Non| F
    D4 --> I
```

---

## 5. Diagramme de séquence — un pas de simulation Mesa

```mermaid
sequenceDiagram
    participant U as Streamlit (temps réel)
    participant M as CityHuntModel
    participant A as PoliceAgent
    participant MEM as SpatialMemory
    participant C as CoordinationManager
    participant D as DecisionEngine
    participant PF as PathFinder (A*)
    participant MV as MovementController
    participant OSM as Réseau OSM

    U->>M: step()
    M->>M: _maybe_spawn_signal()
    M->>A: perceive()
    A->>MEM: add_danger / observation partagée
    M->>A: act()
    A->>C: take_unassigned_signal() / claim_zone()
    C-->>A: signalement attribué
    A->>D: rank_zones(role, memory, step, distances)
    D-->>A: zones classées par score
    A->>PF: find_path(nœud courant, nœud cible, dangers)
    PF->>OSM: graphe de rues (longueurs réelles)
    PF-->>A: itinéraire (liste de nœuds)
    A->>MV: move(agent, speed)
    MV-->>M: nœuds parcourus
    A->>MEM: visit_zone(zone, step)
    M->>M: _resolve_signals() / _check_interceptions()
    M-->>U: DataCollector.collect() → carte OSM rafraîchie
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
    subgraph EXT["Services externes"]
        OVER["Overpass API<br/>(données OSM)"]
        TILES["Tuiles OpenStreetMap<br/>(fond de carte)"]
    end

    subgraph UI["Interface Streamlit (app.py)"]
        W1["Contrôles (sidebar)"]
        W2["st_folium — carte temps réel"]
        W3["Métriques / Mémoire / Journal"]
    end

    subgraph MESA["Moteur Mesa (package cityhunt)"]
        MODEL["CityHuntModel"]
        AG["PoliceAgent / FugitiveAgent / CivilAgent"]
        STRAT["stratégies"]
        DEC["decision_engine"]
        MEM["spatial_memory"]
        ZM["zone_manager"]
        COORD["coordination_manager"]
        SIG["signalement_manager"]
        PF["pathfinding (A*)"]
        MV["movement_controller"]
        RL["rl_module"]
        FOL["map_render (Folium)"]
    end

    subgraph TESTS["Validation"]
        T["pytest — scénarios §14 (hors-ligne)"]
    end

    OVER --> NETW["osm_network"]
    NETW --> MODEL
    UI --> MODEL
    MODEL --> AG
    AG --> STRAT
    STRAT --> DEC
    STRAT --> MEM
    STRAT --> PF
    STRAT --> COORD
    COORD --> SIG
    MODEL --> ZM
    MODEL --> MV
    MODEL --> RL
    MODEL --> FOL
    FOL --> W2
    TILES -.-> W2
    T --> MESA
```

---

## 8. Diagramme de déploiement

```mermaid
flowchart LR
    subgraph NAV["Navigateur de l'utilisateur"]
        LEAF["Leaflet / Folium<br/>tuiles OpenStreetMap"]
    end

    subgraph SERVEUR["Machine hôte (Python 3.10+)"]
        subgraph ST["Processus Streamlit"]
            APP["app.py"]
            CACHE["Cache Streamlit<br/>(réseau OSM)"]
        end
        subgraph PY["Environnement Python"]
            MESA["cityhunt (Mesa SMA)"]
            OSMNX["OSMnx / networkx"]
        end
    end

    OVERPASS["Overpass API"]
    OSM_TILES["tile.openstreetmap.org"]

    APP --> MESA
    MESA --> OSMNX
    OSMNX -->|téléchargement du réseau| OVERPASS
    APP --> CACHE
    LEAF <-->|HTTP| OSM_TILES
    LEAF <-->|WebSocket| ST
```

- **Un seul processus** Streamlit héberge le modèle Mesa ; l'état vit dans `st.session_state`.
- Le **réseau de rues** est téléchargé une seule fois par ville (cache `st.cache_resource`).
- Les **tuiles OpenStreetMap** sont chargées directement par le navigateur (Leaflet).
- Si Overpass est injoignable, `osm_network` bascule sur la grille synthétique : la simulation reste opérationnelle et le fond de carte reste OSM.

---

## 9. Moteur de décision

### 9.1 Scores (§6 de la spécification)

**Police** — `Score(z) = w1·S(z) + w2·P(z) + w3·U(z) − w4·D(z)` (distances en km)

| Terme | Implémentation (`decision_engine.py`) |
|---|---|
| `S(z)` pertinence du signalement | priorité × confiance × fraîcheur des signalements connus |
| `P(z)` probabilité de présence | observations uniquement (signalements, ancienneté de la dernière visite) |
| `U(z)` intérêt d'exploration | 1.0 inconnue, 0.8 à revisiter, sinon décroît avec l'ancienneté |
| `D(z)` coût du déplacement | distance haversine entre centres de zones (km) |

**Fugitif** — `Score(z) = w1·E(z) + w2·S(z) − w3·R(z) − w4·C(z)`

| Terme | Implémentation |
|---|---|
| `E(z)` intérêt d'exploration | identique à `U(z)` |
| `S(z)` sécurité estimée | `1 − danger connu de la zone` |
| `R(z)` risque de rencontre | danger mémorisé (zones où un policier a été vu) |
| `C(z)` coût du déplacement | distance haversine (km) |

Les poids sont ajustables dans la barre latérale Streamlit.

### 9.2 Priorités du cycle (§11)

1. **Police** : signalement attribué → poursuite d'un fugitif **visible** → zones inconnues → revisite / patrouille du secteur assigné.
2. **Fugitif** : fuite si policier ≤ 300 m → zones inconnues sûres → zones connues sûres.
3. **Civil** : nœud voisin aléatoire à chaque pas.

---

## 10. Carte OpenStreetMap et temps réel

- **Chargement** : `osmnx.graph_from_place(place)` (ou `graph_from_point`) télécharge
  le réseau routier réel ; le graphe est simplifié en `nx.Graph` pondéré par la
  longueur réelle des rues (mètres).
- **Rendu** : `map_render.build_map()` produit une carte Folium (tuiles
  OpenStreetMap) avec : rectangles de zones colorés selon la mémoire de
  l'agent sélectionné, marqueurs des agents (🛡️ police, ⚠️ fugitif, 👤 civil),
  PolyLine de l'itinéraire A* courant.
- **Temps réel** : le mode « ⏱️ Temps réel » exécute un pas Mesa puis
  `st.rerun()` — la carte, les marqueurs, les zones et les métriques sont
  rafraîchis à chaque pas selon la cadence choisie.
- **Repli** : sans accès Overpass, une grille Manhattan synthétique centrée sur
  la ville est générée (`load_synthetic_network`) ; l'indicateur « Source du
  réseau » affiche le mode actif.

## 11. Pathfinding A* (§9)

`PathFinder.find_path(start, goal, danger)` — A* networkx sur le graphe de rues :

- `f(n) = g(n) + h(n)` ; poids des arcs = `longueur_rue × (1 + 10 × danger_connu(zone))` ;
- heuristique haversine en mètres (admissible) ;
- recalcul automatique si l'itinéraire devient invalide (F13).

## 12. Apprentissage par renforcement (§12, Phase 7)

`RLModule` : Q-values par zone, `q ← q + α·(r − q)`, récompenses de la spécification
(+5 nouvelle zone, +15 signalement vérifié, +100 interception, −5 déplacement
inutile, +100 évasion, −20 détection). Bonus `0.05 × q[zone]` ajouté au score.
Aucune récompense ne révèle la position d'un adversaire (F12).

## 13. Traçabilité des exigences F01–F15

| ID | Exigence | Implémentation | Test |
|---|---|---|---|
| F01 | Police non aléatoire | `PoliceStrategy.decide` | `test_1`, `test_f01_f02` |
| F02 | Fugitifs non aléatoires | `FugitiveStrategy.decide` | `test_4`, `test_f01_f02` |
| F03 | Civils aléatoires | `CivilStrategy.decide` | `test_f03` |
| F04 | Mémoire individuelle | `SpatialMemory` par agent | tous |
| F05 | Persistance des zones visitées | mémoire jamais réinitialisée | `test_f05_f14` |
| F06 | Zones inconnues prioritaires | candidats + score `U` | `test_1` |
| F07 | Revisite sur événement | `mark_to_revisit` + signalements | `test_2` |
| F08 | Partage d'informations | `CoordinationManager` | `test_3` |
| F09 | Éviter les doublons | `claim_zone`, secteurs | `test_3` |
| F10 | Adaptation aux dangers | `known_dangers`, `_flee` | `test_4` |
| F11 | Obstacles / réseau réel | A* sur le graphe de rues | `test_f11` |
| F12 | Pas d'omniscience | perception haversine à rayon limité | `test_5` |
| F13 | Recalcul des destinations | `route_is_valid` + redécision | `test_f11` |
| F14 | Historique conservé | `exploration_history` | `test_f05_f14` |
| F15 | Amélioration par apprentissage | `RLModule` | `test_interception_possible` |

## 14. Utilisation de l'interface Streamlit

1. **Barre latérale** : ville OpenStreetMap (nom OSM), découpage en zones, rayon,
   effectifs, vitesses, perception (mètres), poids des scores, RL, graine.
2. **▶ 1 pas / ▶▶ 10 pas / ▶▶▶ 50 pas** : avancer la simulation Mesa.
3. **⏱️ Temps réel** : exécution continue avec rafraîchissement de la carte OSM.
4. Onglet **Carte OSM** : sélectionner un agent pour voir **sa** mémoire
   (⬜ inconnue, 🟦 explorée, 🟧 à revisiter) et son itinéraire A* en bleu.
5. Onglets **Métriques**, **Mémoire**, **Journal** : couverture, signalements,
   historique d'exploration, observations partagées, interceptions.

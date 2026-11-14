# 🚓 CityHunt v3.0 — SMA sur carte OpenStreetMap (Mesa)

Système multi-agents de police/fugitifs exécuté sur le **réel réseau de rues
OpenStreetMap** d'une ville, avec le framework **Mesa** :

- **Mémoire spatiale individuelle** par agent stratégique (zones explorées, inconnues, à revisiter)
- **Exploration méthodique** et revisite motivée par les signalements
- **Coordination policière** (secteurs, réservations de zones, partage d'observations)
- **A\*** sur le graphe de rues (networkx) avec surcoûts de danger connus
- **Apprentissage par renforcement** (Q-values par zone, récompenses §12)
- **Interface Streamlit temps réel** : carte Folium/Leaflet avec tuiles OpenStreetMap, marqueurs et itinéraires rafraîchis à chaque pas

> Règle fondamentale : les policiers et les fugitifs ne se déplacent **jamais**
> aléatoirement — seuls les civils conservent un comportement aléatoire.

## Démarrage rapide

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'interface s'ouvre sur `http://localhost:8501`. La carte OSM de la ville
choisie (défaut : Toulouse) est téléchargée via OSMnx/Overpass puis mise en
cache. Si Overpass est inaccessible, un repli hors-ligne (grille synthétique)
garde la simulation fonctionnelle — le fond de carte reste OpenStreetMap.

## Fonctionnalités

| Composant | Comportement |
|---|---|
| Carte | Réseau de rues réel (OSMnx) + rendu Folium sur tuiles OpenStreetMap |
| Moteur | Framework Mesa (`mesa.Model`, agents Mesa, `AgentSet`, `DataCollector`) |
| Police | Investigation des signalements, poursuite des fugitifs visibles, exploration, patrouille de secteur |
| Fugitifs | Fuite stratégique (zone voisine la plus sûre), exploration des zones inconnues sûres |
| Civils | Marche aléatoire de nœud en nœud |
| Zones | Partition géographique de la bbox OSM (grille ajustable) |
| Pathfinding | A* networkx, poids = longueur × (1 + 10 × danger connu) |
| Temps réel | Mode « ⏱️ Temps réel » : un pas de simulation + rafraîchissement de la carte en continu |

## Structure du projet

```
cityhunt/
├── app.py                      # Interface Streamlit (carte OSM temps réel)
├── requirements.txt
├── cityhunt/
│   ├── osm_network.py          # Réseau OSM réel (OSMnx) + repli synthétique
│   ├── zone_manager.py         # Zones géographiques (bbox OSM partitionnée)
│   ├── spatial_memory.py       # Mémoire spatiale individuelle
│   ├── signalement_manager.py  # Cycle de vie des signalements
│   ├── pathfinding.py          # A* networkx sur le réseau de rues
│   ├── decision_engine.py      # Scores police / fugitif (poids ajustables)
│   ├── police_strategy.py      # Stratégie policière
│   ├── fugitive_strategy.py    # Stratégie de fuite
│   ├── civil_strategy.py       # Déplacement aléatoire
│   ├── coordination_manager.py # Partage d'informations policières
│   ├── exploration_manager.py  # Couverture et historique
│   ├── movement_controller.py  # Exécution des déplacements
│   ├── rl_module.py            # Récompenses et Q-values
│   ├── agents.py               # Agents Mesa (Police/Fugitive/Civil)
│   ├── model.py                # CityHuntModel (mesa.Model)
│   └── map_render.py           # Rendu Folium (tuiles OSM, zones, itinéraires)
├── tests/test_scenarios.py     # Les 5 scénarios de validation (§14) + F01–F15
└── docs/DOCUMENTATION.md       # Documentation complète + diagrammes UML
```

## Tests (scénarios de la spécification)

```bash
python -m pytest tests/ -q
```

| Test | Vérification |
|---|---|
| Test 1 | Exploration complète des 16 zones par un policier seul |
| Test 2 | Revisite d'une zone explorée sur nouveau signalement |
| Test 3 | Répartition des secteurs entre 4 policiers, limitation des doublons |
| Test 4 | Fuite stratégique à la détection d'un policier |
| Test 5 | Absence de connaissance omnisciente (F12) |
| + | Mémoire persistante (F05/F14), arcs du chemin A* (F11), interception, intégrité Mesa |

## Documentation

- [Documentation complète](docs/DOCUMENTATION.md) — architecture Mesa/OSM, diagrammes UML (classes, objets, séquence, activité, états, composants, déploiement), scores, exigences F01–F15

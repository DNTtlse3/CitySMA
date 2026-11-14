# 🚓 CityHunt v2.0 — Système multi-agents intelligent

SMA de police/fugitifs en ville : **mémoire spatiale individuelle**, **exploration
méthodique**, **signalements**, **coordination policière**, **pathfinding A\*** et
**apprentissage par renforcement**, avec une interface **Streamlit**.

> Règle fondamentale : les policiers et les fugitifs ne se déplacent **jamais**
> aléatoirement — seuls les civils conservent un comportement aléatoire.

## Démarrage rapide

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'interface s'ouvre sur `http://localhost:8501`.

## Fonctionnalités

| Composant | Comportement |
|---|---|
| Police | Exploration méthodique, investigation des signalements, coordination (secteurs, réservations) |
| Fugitifs | Fuite stratégique, exploration des zones inconnues, évitement des dangers connus |
| Civils | Déplacements aléatoires |
| Mémoire spatiale | `SpatialMemory` individuelle et persistante par agent stratégique |
| Signalements | Cycle `pending → assigned → investigating → resolved / expired`, revisite des zones |
| Pathfinding | A* sur grille avec obstacles et surcoûts de danger |
| Apprentissage | Q-learning tabulaire par zone, récompenses de la spécification §12 |

## Structure du projet

```
cityhunt/
├── app.py                    # Interface Streamlit
├── requirements.txt
├── cityhunt/
│   ├── zone_manager.py       # Zones, voisins, obstacles
│   ├── spatial_memory.py     # Mémoire spatiale individuelle
│   ├── signalement_manager.py# Cycle de vie des signalements
│   ├── pathfinding.py        # A*
│   ├── decision_engine.py    # Scores police / fugitif (poids ajustables)
│   ├── police_strategy.py    # Stratégie policière
│   ├── fugitive_strategy.py  # Stratégie de fuite
│   ├── civil_strategy.py     # Déplacement aléatoire
│   ├── coordination_manager.py # Partage d'informations policières
│   ├── exploration_manager.py  # Couverture et historique
│   ├── movement_controller.py  # Exécution des déplacements
│   ├── rl_module.py          # Récompenses et Q-values
│   ├── agents.py             # Agents et fabrique
│   ├── environment.py        # Perception, événements, pas de simulation
│   └── simulation.py         # Configuration et boucle de simulation
├── tests/test_scenarios.py   # Les 5 scénarios de validation (§14)
└── docs/
    ├── DOCUMENTATION.md      # Documentation complète + diagrammes UML
    └── ARCHITECTURE.md       # Diagrammes d'architecture et de déploiement
```

## Tests (scénarios de la spécification)

```bash
python -m pytest tests/ -q
```

| Test | Vérification |
|---|---|
| Test 1 | Exploration complète des 20 zones par un policier seul |
| Test 2 | Revisite d'une zone explorée sur nouveau signalement |
| Test 3 | Répartition des secteurs entre 4 policiers, limitation des doublons |
| Test 4 | Fuite stratégique à la détection d'un policier |
| Test 5 | Absence de connaissance omnisciente (F12) |
| + | Persistence de la mémoire (F05/F14), obstacles en A* (F11), interception |

## Documentation

- [Documentation complète](docs/DOCUMENTATION.md) — architecture, diagrammes UML (classes, objets, séquence, activité, états, composants, déploiement), scores, exigences F01–F15

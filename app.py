"""CityHunt v3 — Interface Streamlit temps réel sur carte OpenStreetMap.

Moteur SMA : Mesa · Carte : tuiles OpenStreetMap (Folium/Leaflet)
Lancement :  streamlit run app.py
"""

from __future__ import annotations

import time

import streamlit as st
from streamlit_folium import st_folium

from cityhunt import __version__
from cityhunt.decision_engine import FugitiveWeights, PoliceWeights
from cityhunt.map_render import build_map
from cityhunt.model import CityHuntModel
from cityhunt.osm_network import load_city_network, load_synthetic_network
from cityhunt.spatial_memory import EXPLORED, TO_REVISIT, UNKNOWN

st.set_page_config(page_title="CityHunt", page_icon="🚓", layout="wide")

st.title(f"🚓 CityHunt v{__version__} — SMA sur carte OpenStreetMap")
st.caption("Moteur Mesa · mémoire spatiale individuelle · exploration méthodique · "
           "coordination · A* sur le réseau de rues · renforcement")


# --------------------------------------------------------------------------- #
# Chargement de la carte (mise en cache)                                       #
# --------------------------------------------------------------------------- #

@st.cache_resource(show_spinner="Chargement du réseau OpenStreetMap…")
def load_city(place: str, dist_m: int, lat: float = 0.0, lon: float = 0.0) -> tuple:
    if lat and lon:
        network = load_city_network(center=(lat, lon), dist_m=dist_m)
    else:
        network = load_city_network(place=place, dist_m=dist_m)
    return network, network.source


@st.cache_resource(show_spinner=False)
def load_fallback(place: str, seed: int) -> tuple:
    network = load_synthetic_network(seed=seed)
    return network, network.source


# --------------------------------------------------------------------------- #
# Barre latérale                                                               #
# --------------------------------------------------------------------------- #

def sidebar() -> None:
    st.sidebar.subheader("🗺️ Carte OpenStreetMap")
    st.sidebar.text_input("Ville (nom OSM)", "Toulouse, France", key="place",
                          help="Ex. : Saint-André, Réunion, France")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("Latitude (option)", -90.0, 90.0, 0.0, 0.0001,
                    key="center_lat", format="%.5f",
                    help="Si lat et lon ≠ 0, priorité sur le nom de ville. "
                         "Saint-André (Réunion) : -20.9606, 55.6493")
    c2.number_input("Longitude (option)", -180.0, 180.0, 0.0, 0.0001,
                    key="center_lon", format="%.5f")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("Zones en X", 1, 10, 4, key="zone_cols")
    c2.number_input("Zones en Y", 1, 10, 4, key="zone_rows")
    st.sidebar.number_input("Rayon de la zone (m)", 300, 20000, 2000, 100, key="dist_m",
                            help="Rayon autour du point central (mode coordonnées)")

    st.sidebar.subheader("Agents")
    c1, c2, c3 = st.sidebar.columns(3)
    c1.number_input("Police", 0, 12, 4, key="n_police")
    c2.number_input("Fugitifs", 0, 12, 2, key="n_fugitives")
    c3.number_input("Civils", 0, 40, 6, key="n_civilians")
    c1, c2, c3 = st.sidebar.columns(3)
    c1.number_input("Vitesse police", 1, 6, 2, key="police_speed")
    c2.number_input("Vitesse fugitifs", 1, 6, 3, key="fugitive_speed")
    c3.number_input("Vitesse civils", 1, 6, 1, key="civilian_speed")
    st.sidebar.slider("Rayon de perception (m)", 50, 1000, 250, 50, key="perception_m")

    st.sidebar.subheader("Signalements")
    st.sidebar.number_input("Intervalle (pas)", 5, 100, 15, key="signal_interval")
    st.sidebar.slider("Probabilité", 0.0, 1.0, 0.5, 0.05, key="signal_probability")

    st.sidebar.subheader("Poids — Police")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("w1 Signalement", 0.0, 10.0, 5.0, 0.5, key="w_signal")
    c2.number_input("w2 Présence", 0.0, 10.0, 3.0, 0.5, key="w_presence")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("w3 Exploration", 0.0, 10.0, 2.0, 0.5, key="w_pexploration")
    c2.number_input("w4 Distance", 0.0, 5.0, 0.5, 0.1, key="w_pdistance")

    st.sidebar.subheader("Poids — Fugitif")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("w1 Exploration", 0.0, 10.0, 2.0, 0.5, key="w_fexploration")
    c2.number_input("w2 Sécurité", 0.0, 10.0, 3.0, 0.5, key="w_safety")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("w3 Risque", 0.0, 10.0, 4.0, 0.5, key="w_risk")
    c2.number_input("w4 Distance", 0.0, 5.0, 0.5, 0.1, key="w_fdistance")

    st.sidebar.subheader("Apprentissage")
    st.sidebar.toggle("Renforcement activé (Phase 7)", key="rl_enabled", value=True)
    st.sidebar.number_input("Graine aléatoire", 0, 9999, 42, key="seed")


def build_model() -> CityHuntModel:
    c = st.session_state
    try:
        network, source = load_city(c["place"], c["dist_m"],
                                    c["center_lat"], c["center_lon"])
    except Exception:
        network, source = load_fallback(c["place"], c["seed"])
    st.session_state.map_source = source
    model = CityHuntModel(
        network=network,
        zone_cols=c["zone_cols"], zone_rows=c["zone_rows"],
        n_police=c["n_police"], n_fugitives=c["n_fugitives"], n_civilians=c["n_civilians"],
        police_speed=c["police_speed"], fugitive_speed=c["fugitive_speed"],
        civilian_speed=c["civilian_speed"], perception_m=c["perception_m"],
        seed=c["seed"], signal_interval=c["signal_interval"],
        signal_probability=c["signal_probability"], rl_enabled=c["rl_enabled"],
        police_weights=PoliceWeights(
            signal=c["w_signal"], presence=c["w_presence"],
            exploration=c["w_pexploration"], distance=c["w_pdistance"]),
        fugitive_weights=FugitiveWeights(
            exploration=c["w_fexploration"], safety=c["w_safety"],
            risk=c["w_risk"], cost=c["w_fdistance"]),
    )
    st.session_state.model = model
    return model


def get_model() -> CityHuntModel:
    if "model" not in st.session_state:
        build_model()
    return st.session_state.model


# --------------------------------------------------------------------------- #
# Onglets                                                                      #
# --------------------------------------------------------------------------- #

def tab_map(model: CityHuntModel) -> None:
    strategic = model.strategic_agents()
    options = ["— Vue globale —"] + [a.name for a in strategic]
    focus_name = st.selectbox("Afficher la mémoire et l'itinéraire de :", options,
                              key="focus_agent")
    focus = next((a for a in strategic if a.name == focus_name), None)

    col_map, col_side = st.columns([3, 1])
    with col_map:
        st_folium(build_map(model, focus), width=None, height=560,
                  returned_objects=[], key="osm_map")
        st.caption("Zones (mémoire de l'agent sélectionné) : ⬜ inconnue · 🟦 explorée · "
                   "🟧 à revisiter · 🔵 itinéraire A* · 🛡️ police · ⚠️ fugitif · 👤 civil")
    with col_side:
        st.metric("Pas de simulation", model.step_count)
        st.metric("Couverture globale", f"{model.global_coverage() * 100:.0f}%")
        st.metric("Signalements actifs", len(model.signalements.pending(model.step_count)))
        st.metric("Interceptions", len(model.captures))
        st.metric("Fugitifs en fuite", sum(1 for a in model.fugitives() if a.alive))
        src = st.session_state.get("map_source", model.network.source)
        st.info(f"Source du réseau : **{'OSM réel' if src == 'osm' else 'grille synthétique (repli hors-ligne)'}**",
                icon="🛰️" if src == "osm" else "🧪")
        if focus:
            st.divider()
            st.markdown(f"**{focus.name}**")
            st.progress(focus.memory.exploration_ratio(),
                        text=f"Exploré : {focus.memory.exploration_ratio() * 100:.0f}%")
            st.write(f"Historique : {len(focus.memory.exploration_history)} visites")
            st.write(f"Zones inconnues : {len(focus.memory.unvisited_zones)}")
            st.write(f"Dangers connus : {list(focus.memory.known_dangers.keys())}")


def tab_metrics(model: CityHuntModel) -> None:
    import pandas as pd

    df = pd.DataFrame(model.datacollector.model_vars)
    if df.empty:
        st.info("Lancez quelques pas de simulation.")
        return
    df.index.name = "step"
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Couverture de l'exploration")
        st.line_chart(df["coverage"], height=300)
    with c2:
        st.subheader("Signalements")
        st.line_chart(df[["signals_pending", "signals_total"]], height=300)
    st.subheader("Résumé")
    st.json(model.summary(), expanded=True)


def tab_memory(model: CityHuntModel) -> None:
    strategic = model.strategic_agents()
    if not strategic:
        st.info("Aucun agent stratégique.")
        return
    agent = st.selectbox("Agent :", strategic, format_func=lambda a: a.name, key="mem_agent")
    m = agent.memory
    c1, c2, c3 = st.columns(3)
    c1.metric("Zones explorées", len(m.visited_zones))
    c2.metric("Zones inconnues", len(m.unvisited_zones))
    c3.metric("Signalements connus", len(m.known_signals))
    st.markdown("**Historique d'exploration (30 dernières visites)**")
    st.code(" → ".join(f"Z{z}" for z in m.exploration_history[-30:]) or "—", language=None)
    st.markdown("**Derniers événements de renforcement**")
    for step, event, r in agent.rl.events[-10:][::-1]:
        st.write(f"pas {step} · `{event}` · {r:+.0f}")


def tab_log(model: CityHuntModel) -> None:
    st.markdown("**Historique d'exploration global** (extrait)")
    for row in model.exploration.history[-25:][::-1]:
        st.write(f"pas {row['step']} · {row['agent']} · Z{row['zone']} · {row['event']}")
    st.markdown("**Observations partagées (coordination policière)**")
    for obs in model.coordination.last_observations[-10:][::-1]:
        st.write(f"pas {obs['step']} · {obs['agent']} · Z{obs['zone']} · {obs['kind']}")
    if model.captures:
        st.markdown("**Interceptions**")
        for c in model.captures:
            st.write(f"pas {c['step']} · {c['police']} a intercepté {c['fugitive']} en Z{c['zone']}")


# --------------------------------------------------------------------------- #
# Application                                                                  #
# --------------------------------------------------------------------------- #

def main() -> None:
    sidebar()
    model = get_model()

    controls = st.columns(5)
    if controls[0].button("▶ 1 pas", use_container_width=True):
        model.step()
    if controls[1].button("▶▶ 10 pas", use_container_width=True):
        for _ in range(10):
            model.step()
    if controls[2].button("▶▶▶ 50 pas", use_container_width=True):
        for _ in range(50):
            model.step()
    auto = controls[3].toggle("⏱️ Temps réel", value=False)
    speed = controls[4].slider("Cadence", 0.0, 1.0, 0.5, 0.1, label_visibility="collapsed")

    if auto:
        model.step()
        time.sleep(max(0.05, 1.2 - speed))

    c1, c2 = st.columns(2)
    if c1.button("🔄 Nouvelle simulation (recharger la carte)"):
        st.cache_resource.clear()
        build_model()
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Carte OSM", "📈 Métriques", "🧠 Mémoire", "📜 Journal"])
    with tab1:
        tab_map(model)
    with tab2:
        tab_metrics(model)
    with tab3:
        tab_memory(model)
    with tab4:
        tab_log(model)

    if auto:
        st.rerun()


if __name__ == "__main__":
    main()

"""CityHunt — Interface Streamlit.

Lancement :  streamlit run app.py
"""

from __future__ import annotations

import time

import plotly.graph_objects as go
import streamlit as st

from cityhunt import __version__
from cityhunt.decision_engine import FugitiveWeights, PoliceWeights
from cityhunt.simulation import Simulation, SimulationConfig
from cityhunt.spatial_memory import EXPLORED, TO_REVISIT, UNKNOWN

st.set_page_config(page_title="CityHunt", page_icon="🚓", layout="wide")

ZONE_COLORS = {
    UNKNOWN: "#f0f2f6",
    EXPLORED: "#c6e2ff",
    TO_REVISIT: "#ffd27f",
}
AGENT_STYLE = {
    "police": {"color": "#1f5fd0", "symbol": "star-square", "label": "Police"},
    "fugitive": {"color": "#d62728", "symbol": "triangle-up", "label": "Fugitif"},
    "civil": {"color": "#2ca02c", "symbol": "circle", "label": "Civil"},
}


def default_config() -> SimulationConfig:
    return SimulationConfig()


def new_simulation() -> Simulation:
    c = st.session_state
    cfg = SimulationConfig(
        width=c["width"], height=c["height"],
        zone_cols=c["zone_cols"], zone_rows=c["zone_rows"],
        obstacle_rate=c["obstacle_rate"],
        n_police=c["n_police"], n_fugitives=c["n_fugitives"], n_civilians=c["n_civilians"],
        police_speed=c["police_speed"], fugitive_speed=c["fugitive_speed"],
        civilian_speed=c["civilian_speed"],
        perception_radius=c["perception_radius"],
        seed=c["seed"],
        signal_interval=c["signal_interval"], signal_probability=c["signal_probability"],
        rl_enabled=c["rl_enabled"],
        police_weights=PoliceWeights(
            signal=c["w_signal"], presence=c["w_presence"],
            exploration=c["w_pexploration"], distance=c["w_pdistance"],
        ),
        fugitive_weights=FugitiveWeights(
            exploration=c["w_fexploration"], safety=c["w_safety"],
            risk=c["w_risk"], cost=c["w_fdistance"],
        ),
    )
    sim = Simulation(cfg)
    sim._record()
    st.session_state.sim = sim
    return sim


def get_sim() -> Simulation:
    if "sim" not in st.session_state:
        st.session_state.sim = new_simulation()
    return st.session_state.sim


# --------------------------------------------------------------------------- #
# Barre latérale                                                               #
# --------------------------------------------------------------------------- #

def sidebar() -> None:
    st.sidebar.title(f"🚓 CityHunt v{__version__}")
    st.sidebar.caption("SMA : mémoire spatiale, exploration méthodique, coordination")

    st.sidebar.subheader("Monde")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("Largeur (cellules)", 10, 60, 20, key="width")
    c2.number_input("Hauteur (cellules)", 10, 60, 20, key="height")
    c1, c2 = st.sidebar.columns(2)
    c1.number_input("Zones en X", 1, 10, 5, key="zone_cols")
    c2.number_input("Zones en Y", 1, 10, 4, key="zone_rows")
    st.sidebar.slider("Densité d'obstacles", 0.0, 0.25, 0.08, 0.01, key="obstacle_rate")
    st.sidebar.number_input("Graine aléatoire", 0, 9999, 42, key="seed")

    st.sidebar.subheader("Agents")
    c1, c2, c3 = st.sidebar.columns(3)
    c1.number_input("Police", 0, 10, 4, key="n_police")
    c2.number_input("Fugitifs", 0, 10, 2, key="n_fugitives")
    c3.number_input("Civils", 0, 30, 6, key="n_civilians")
    c1, c2, c3 = st.sidebar.columns(3)
    c1.number_input("Vitesse police", 1, 5, 2, key="police_speed")
    c2.number_input("Vitesse fugitifs", 1, 5, 3, key="fugitive_speed")
    c3.number_input("Vitesse civils", 1, 5, 1, key="civilian_speed")
    st.sidebar.slider("Rayon de perception", 1, 12, 5, key="perception_radius")

    st.sidebar.subheader("Signalements")
    st.sidebar.number_input("Intervalle d'apparition (pas)", 5, 100, 15, key="signal_interval")
    st.sidebar.slider("Probabilité d'apparition", 0.0, 1.0, 0.5, 0.05, key="signal_probability")

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

    if st.sidebar.button("🔄 Nouvelle simulation", type="primary", use_container_width=True):
        new_simulation()

    st.sidebar.divider()
    st.sidebar.caption(
        "Police et fugitifs : déplacements **stratégiques** (mémoire spatiale + A*).\n\n"
        "Civils : déplacements **aléatoires**.")


# --------------------------------------------------------------------------- #
# Rendu de la carte                                                            #
# --------------------------------------------------------------------------- #

def draw_map(sim: Simulation, focus_agent_id: str | None) -> go.Figure:
    env = sim.environment
    zn = env.zone_manager
    fig = go.Figure()

    focus = next((a for a in env.agents if a.id == focus_agent_id), None)
    for zone in zn.zones.values():
        x0, y0, x1, y1 = zone.bounds
        state = focus.memory.state_of(zone.id) if focus and focus.is_strategic else UNKNOWN
        fill = ZONE_COLORS.get(state, "#f0f2f6")
        fig.add_shape(type="rect", x0=x0 - 0.5, y0=y0 - 0.5, x1=x1 + 0.5, y1=y1 + 0.5,
                      fillcolor=fill, line=dict(color="#9aa5b1", width=1), layer="below")
        fig.add_annotation(x=(x0 + x1) / 2, y=y0 - 0.62, text=f"Z{zone.id}",
                           showarrow=False, font=dict(size=9, color="#556"))
        for (ox, oy) in zn.obstacles:
            if zone.contains((ox, oy)):
                fig.add_shape(type="rect", x0=ox - 0.5, y0=oy - 0.5, x1=ox + 0.5, y1=oy + 0.5,
                              fillcolor="#3b4252", line=dict(width=0), layer="below")

    for agent in env.alive_agents():
        style = AGENT_STYLE[agent.role]
        fig.add_trace(go.Scatter(
            x=[agent.position[0]], y=[agent.position[1]],
            mode="markers+text", text=[agent.id.split("-")[0]], textposition="top center",
            textfont=dict(size=8),
            marker=dict(size=16, color=style["color"], symbol=style["symbol"],
                        line=dict(width=1, color="white")),
            name=agent.id, legendgroup=agent.role,
            showlegend=focus_agent_id is None,
        ))

    fig.update_layout(
        height=620, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(range=[-0.8, zn.width - 0.2], visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(range=[-0.8, zn.height - 0.2], visible=False, autorange="reversed"),
        legend=dict(orientation="h", y=-0.02, x=0),
        uirevision="map",
    )
    return fig


# --------------------------------------------------------------------------- #
# Onglets                                                                      #
# --------------------------------------------------------------------------- #

def tab_map(sim: Simulation) -> None:
    env = sim.environment
    strategic = [a for a in env.agents if a.is_strategic]
    options = [a.id for a in strategic]
    focus_id = st.selectbox(
        "Afficher la mémoire spatiale de :", ["— Vue globale —"] + options,
        key="focus_agent")
    focus_id = None if focus_id.startswith("—") else focus_id

    col_map, col_side = st.columns([3, 1])
    with col_map:
        st.plotly_chart(draw_map(sim, focus_id), use_container_width=True)
        st.caption("Zones (vue agent) : ⬜ inconnue · 🟦 explorée · 🟧 à revisiter · ⬛ obstacle")
    with col_side:
        st.metric("Pas de simulation", env.step_count)
        st.metric("Couverture globale",
                  f"{env.exploration.global_coverage(env.strategic_agents()) * 100:.0f}%")
        st.metric("Signalements actifs", len(env.signalements.pending(env.step_count)))
        st.metric("Interceptions", len(env.captures))
        st.metric("Fugitifs en fuite", sum(1 for a in env.agents if a.role == "fugitive" and a.alive))
        if focus_id:
            agent = next(a for a in env.agents if a.id == focus_id)
            st.divider()
            st.markdown(f"**{agent.id}**")
            st.progress(agent.memory.exploration_ratio(),
                        text=f"Exploré : {agent.memory.exploration_ratio() * 100:.0f}%")
            st.write(f"Historique : {len(agent.memory.exploration_history)} visites")
            st.write(f"Zones inconnues : {len(agent.memory.unvisited_zones)}")
            st.write(f"Dangers connus : {list(agent.memory.known_dangers.keys())}")
            st.write(f"Q top : {agent.rl.top_zones(3)}")


def tab_metrics(sim: Simulation) -> None:
    import pandas as pd

    if not sim.metrics:
        st.info("Lancez quelques pas de simulation.")
        return
    df = pd.DataFrame(sim.metrics)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Couverture de l'exploration")
        st.line_chart(df.set_index("step")["coverage"], height=300)
    with c2:
        st.subheader("Signalements")
        st.line_chart(df.set_index("step")[["signals_pending", "signals_total"]], height=300)

    st.subheader("Résumé")
    st.json(sim.summary(), expanded=True)


def tab_memory(sim: Simulation) -> None:
    strategic = [a for a in sim.environment.agents if a.is_strategic]
    if not strategic:
        st.info("Aucun agent stratégique.")
        return
    agent = st.selectbox("Agent :", strategic, format_func=lambda a: a.id, key="mem_agent")
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


def tab_log(sim: Simulation) -> None:
    env = sim.environment
    st.markdown("**Historique d'exploration global** (extrait)")
    rows = env.exploration.history[-25:][::-1]
    for row in rows:
        st.write(f"pas {row['step']} · {row['agent']} · Z{row['zone']} · {row['event']}")
    st.markdown("**Observations partagées (coordination policière)**")
    for obs in env.coordination.last_observations[-10:][::-1]:
        st.write(f"pas {obs['step']} · {obs['agent']} · Z{obs['zone']} · {obs['kind']}")
    if env.captures:
        st.markdown("**Interceptions**")
        for c in env.captures:
            st.write(f"pas {c['step']} · {c['police']} a intercepté {c['fugitive']} en Z{c['zone']}")


# --------------------------------------------------------------------------- #
# Application                                                                  #
# --------------------------------------------------------------------------- #

def main() -> None:
    sidebar()
    sim = get_sim()

    controls = st.columns(5)
    if controls[0].button("▶ 1 pas", use_container_width=True):
        sim.step_once()
    if controls[1].button("▶▶ 10 pas", use_container_width=True):
        sim.run(10)
    if controls[2].button("▶▶▶ 50 pas", use_container_width=True):
        sim.run(50)
    auto = controls[3].toggle("Lecture auto", value=False)
    speed = controls[4].slider("Vitesse", 0.0, 1.0, 0.5, 0.1,
                               label_visibility="collapsed")

    if auto:
        sim.run(1)
        time.sleep(1.1 - speed)

    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Carte", "📈 Métriques", "🧠 Mémoire", "📜 Journal"])
    with tab1:
        tab_map(sim)
    with tab2:
        tab_metrics(sim)
    with tab3:
        tab_memory(sim)
    with tab4:
        tab_log(sim)

    if auto:
        st.rerun()


if __name__ == "__main__":
    main()

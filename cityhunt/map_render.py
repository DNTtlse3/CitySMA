"""Rendu Folium de la simulation sur tuiles OpenStreetMap (module map_render).

La carte de fond est toujours OpenStreetMap ; les zones sont dessinées comme
des rectangles colorés selon la mémoire de l'agent sélectionné, les agents
apparaissent comme des marqueurs et l'itinéraire de l'agent sélectionné est
tracé en PolyLine.
"""

from __future__ import annotations

import folium

from .spatial_memory import EXPLORED, TO_REVISIT, UNKNOWN

ZONE_COLORS = {
    UNKNOWN: "#f7f7f7",
    EXPLORED: "#c6e2ff",
    TO_REVISIT: "#ffd27f",
}

ROLE_STYLE = {
    "police": {"color": "blue", "icon": "shield", "prefix": "glyphicon"},
    "fugitive": {"color": "red", "icon": "warning-sign", "prefix": "glyphicon"},
    "civil": {"color": "green", "icon": "user", "prefix": "glyphicon"},
}


def build_map(model, focus_agent=None, path_on_map: bool = True) -> folium.Map:
    network = model.network
    lat0, lon0 = network.center
    m = folium.Map(location=[lat0, lon0], zoom_start=15, tiles="OpenStreetMap",
                   control_scale=True)

    for zone in model.zones.zones.values():
        state = UNKNOWN
        if focus_agent is not None and focus_agent.is_strategic:
            state = focus_agent.memory.state_of(zone.id)
        lat_min, lat_max, lon_min, lon_max = zone.bounds
        folium.Rectangle(
            bounds=[[lat_min, lon_min], [lat_max, lon_max]],
            color="#9aa5b1", weight=1,
            fill=True, fill_color=ZONE_COLORS[state], fill_opacity=0.35,
            tooltip=f"Zone {zone.id} · {state}",
        ).add_to(m)

    if path_on_map and focus_agent is not None and focus_agent.path:
        points = [list(focus_agent.coords())] + \
            [list(network.coords(n)) for n in focus_agent.path]
        folium.PolyLine(points, color="#1f5fd0", weight=4, opacity=0.8,
                        tooltip="Itinéraire A*").add_to(m)

    for agent in model.agents:
        if not agent.alive:
            continue
        lat, lon = agent.coords()
        style = ROLE_STYLE[agent.role]
        folium.Marker(
            [lat, lon],
            icon=folium.Icon(color=style["color"], icon=style["icon"], prefix=style["prefix"]),
            tooltip=f"{agent.name} · Zone {agent.current_zone}",
            popup=folium.Popup(
                f"<b>{agent.name}</b><br>Rôle : {agent.role}"
                f"<br>Zone : {agent.current_zone}"
                f"<br>Vitesse : {agent.speed} nœuds/pas"
                f"<br>Zones explorées : {len(agent.memory.visited_zones)}"
                f"<br>Récompense RL : {agent.rl.cumulative_reward:+.0f}",
                max_width=220,
            ),
        ).add_to(m)

    return m

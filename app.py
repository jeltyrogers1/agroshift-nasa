from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import folium
from folium.plugins import Draw
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_folium import st_folium

from src.agroshift_engine import simulate_scenarios


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
CLIMATOLOGY_PATH = DATA_DIR / "agroshift_climatology_12m.json"
CULTIVOS_PATH = DATA_DIR / "cultivos_coahuila_clean.json"
SUELOS_PATH = DATA_DIR / "suelos_coahuila_clean.json"

PLOT_OPTIONS = [
    "UAAAN_La_Narro",
    "Los_Lirios_Arteaga",
    "General_Cepeda",
]

PLOT_DISPLAY_NAMES = {
    "UAAAN_La_Narro": "UAAAN La Narro (Saltillo)",
    "Los_Lirios_Arteaga": "Los Lirios (Arteaga)",
    "General_Cepeda": "General Cepeda",
}

DARK_CSS = """
<style>
    .stApp {
        background-color: #0b111e;
        color: #e2e8f0;
    }
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
    .agro-hero {
        background: linear-gradient(135deg, #0f172a 0%, #16243d 60%, #0d2a2f 100%);
        border: 1px solid #1e3a5f;
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
    }
    .agro-badge-nasa {
        display: inline-block;
        background: rgba(56, 189, 248, 0.14);
        border: 1px solid #38bdf8;
        color: #7dd3fc;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 0.22rem 0.65rem;
        border-radius: 999px;
        margin-bottom: 0.5rem;
    }
    .agro-title {
        font-size: 1.85rem;
        font-weight: 800;
        color: #f8fafc;
        margin: 0.1rem 0 0.2rem 0;
        line-height: 1.2;
    }
    .agro-subtitle {
        font-size: 0.96rem;
        color: #94a3b8;
        margin: 0;
    }
    .kpi-card {
        background-color: #121c2e;
        border: 1px solid #1f324d;
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
        height: 100%;
    }
    .kpi-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 0.2rem;
    }
    .kpi-value {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f1f5f9;
        line-height: 1.25;
    }
    .kpi-sub {
        font-size: 0.76rem;
        color: #38bdf8;
        margin-top: 0.15rem;
    }
    .problem-banner {
        background: rgba(245, 158, 11, 0.10);
        border-left: 4px solid #f59e0b;
        border-radius: 6px;
        padding: 0.65rem 0.95rem;
        margin: 0.7rem 0 1.1rem 0;
        color: #fde68a;
        font-size: 0.9rem;
    }
    .plan-card {
        background-color: #121c2e;
        border: 1px solid #1f324d;
        border-radius: 14px;
        padding: 1.05rem 1.1rem;
        margin-bottom: 0.85rem;
    }
    .plan-card-recommended {
        background: linear-gradient(180deg, #132530 0%, #121c2e 100%);
        border: 2px solid #22c55e;
        box-shadow: 0 0 18px rgba(34, 197, 94, 0.18);
    }
    .rec-ribbon {
        background: linear-gradient(90deg, #16a34a, #22c55e);
        color: #04130a;
        font-weight: 800;
        font-size: 0.76rem;
        text-align: center;
        letter-spacing: 0.05em;
        padding: 0.3rem 0.6rem;
        border-radius: 8px;
        margin-bottom: 0.65rem;
        text-transform: uppercase;
    }
    .baseline-ribbon {
        background: rgba(148, 163, 184, 0.15);
        color: #cbd5e1;
        font-weight: 700;
        font-size: 0.74rem;
        text-align: center;
        letter-spacing: 0.04em;
        padding: 0.3rem 0.6rem;
        border-radius: 8px;
        margin-bottom: 0.65rem;
        text-transform: uppercase;
    }
    .plan-header {
        font-size: 1.12rem;
        font-weight: 800;
        color: #f8fafc;
        margin-bottom: 0.2rem;
    }
    .plan-focus {
        font-size: 0.82rem;
        color: #94a3b8;
        min-height: 2.3rem;
        margin-bottom: 0.6rem;
    }
    .score-pill {
        display: inline-block;
        background: rgba(56, 189, 248, 0.15);
        border: 1px solid #38bdf8;
        color: #e0f2fe;
        font-size: 0.92rem;
        font-weight: 800;
        padding: 0.22rem 0.65rem;
        border-radius: 8px;
        margin-bottom: 0.65rem;
    }
    .semaforo-grid {
        display: flex;
        gap: 0.45rem;
        margin: 0.45rem 0 0.75rem 0;
        flex-wrap: wrap;
    }
    .sem-pill {
        flex: 1;
        min-width: 82px;
        text-align: center;
        border-radius: 8px;
        padding: 0.35rem 0.45rem;
        font-size: 0.75rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .sem-VERDE {
        background-color: #064e3b;
        border: 1px solid #10b981;
        color: #6ee7b7;
    }
    .sem-AMARILLO {
        background-color: #78350f;
        border: 1px solid #f59e0b;
        color: #fde68a;
    }
    .sem-ROJO {
        background-color: #7f1d1d;
        border: 1px solid #ef4444;
        color: #fca5a5;
    }
    .metric-box {
        background-color: #0d1524;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 0.55rem 0.7rem;
        margin-bottom: 0.45rem;
    }
    .metric-box-label {
        font-size: 0.72rem;
        color: #94a3b8;
        text-transform: uppercase;
    }
    .metric-box-val {
        font-size: 1.08rem;
        font-weight: 800;
        color: #f8fafc;
    }
    .nasa-evidence-box {
        background: rgba(56, 189, 248, 0.08);
        border: 1px solid #1d4ed8;
        border-left: 4px solid #38bdf8;
        border-radius: 8px;
        padding: 0.7rem 0.85rem;
        margin-top: 0.65rem;
        font-size: 0.84rem;
        line-height: 1.45;
        color: #dbeafe;
    }
    .section-title {
        font-size: 1.2rem;
        font-weight: 800;
        color: #f8fafc;
        margin: 0.9rem 0 0.45rem 0;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 0.3rem;
    }
</style>
"""


def _load_reference_data_raw() -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Load processed climatology, soil, and crop datasets from disk."""
    with CLIMATOLOGY_PATH.open("r", encoding="utf-8") as f:
        climatology = json.load(f)
    with SUELOS_PATH.open("r", encoding="utf-8") as f:
        suelos_list = json.load(f)
    with CULTIVOS_PATH.open("r", encoding="utf-8") as f:
        cultivos_list = json.load(f)

    suelos_dict = {s["location_id"]: s for s in suelos_list}
    return climatology, suelos_dict, cultivos_list


@st.cache_data
def load_reference_data() -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    return _load_reference_data_raw()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers using the Haversine formula."""
    earth_radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return earth_radius_km * c


def calculate_polygon_area_hectares(coords: list[list[float]]) -> tuple[float, float, float]:
    """
    Compute geodesic-projected polygon area in hectares and centroid (lat, lon)
    from a GeoJSON outer ring of [lon, lat] vertices.
    """
    if len(coords) < 3:
        raise ValueError("El polígono debe tener al menos 3 vértices.")

    ring = list(coords)
    if ring[0] == ring[-1] and len(ring) > 3:
        unique_pts = ring[:-1]
    else:
        unique_pts = ring
        ring = ring + [ring[0]]

    centroid_lon = sum(pt[0] for pt in unique_pts) / len(unique_pts)
    centroid_lat = sum(pt[1] for pt in unique_pts) / len(unique_pts)

    lat_rad = math.radians(centroid_lat)
    m_per_deg_lat = (
        111132.954
        - 559.822 * math.cos(2.0 * lat_rad)
        + 1.175 * math.cos(4.0 * lat_rad)
    )
    m_per_deg_lon = (
        111412.84 * math.cos(lat_rad)
        - 93.5 * math.cos(3.0 * lat_rad)
    )

    projected: list[tuple[float, float]] = []
    for lon, lat in ring:
        x_m = (lon - centroid_lon) * m_per_deg_lon
        y_m = (lat - centroid_lat) * m_per_deg_lat
        projected.append((x_m, y_m))

    twice_area = 0.0
    for i in range(len(projected) - 1):
        x1, y1 = projected[i]
        x2, y2 = projected[i + 1]
        twice_area += (x1 * y2) - (x2 * y1)

    area_m2 = abs(twice_area) / 2.0
    area_ha = max(0.1, round(area_m2 / 10000.0, 2))
    return area_ha, centroid_lat, centroid_lon


def find_nearest_station(
    lat: float,
    lon: float,
    suelos_dict: dict[str, dict[str, Any]],
) -> tuple[str, float]:
    """Find the closest calibrated Coahuila station using Haversine distance."""
    nearest_id = ""
    nearest_dist = float("inf")
    for loc_id, soil in suelos_dict.items():
        dist = haversine_km(lat, lon, float(soil["latitud"]), float(soil["longitud"]))
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_id = loc_id
    return nearest_id, round(nearest_dist, 2)


def build_satellite_map(
    selected_location_id: str,
    suelos_dict: dict[str, dict[str, Any]],
) -> folium.Map:
    """Create a Folium satellite map centered on the active plot with polygon drawing tools."""
    active_soil = suelos_dict[selected_location_id]
    center_lat = float(active_soil["latitud"])
    center_lon = float(active_soil["longitud"])

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        control_scale=True,
        tiles=None,
    )

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satélite (Esri World Imagery)",
        overlay=False,
        control=True,
    ).add_to(fmap)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB DarkMatter",
        name="Mapa Oscuro",
        overlay=False,
        control=True,
    ).add_to(fmap)

    for loc_id, soil in suelos_dict.items():
        is_active = loc_id == selected_location_id
        marker_color = "#22c55e" if is_active else "#38bdf8"
        popup_html = (
            f"<b>{soil['zona_label']}</b><br>"
            f"Suelo: {soil['tipo_suelo_label']} ({soil['textura_label']})<br>"
            f"Elevación: {soil['local_elevation_m']:.0f} msnm<br>"
            f"MO: {soil['materia_organica_pct']}% | Retención: {soil['retencion_agua']}"
        )
        folium.CircleMarker(
            location=[float(soil["latitud"]), float(soil["longitud"])],
            radius=10 if is_active else 7,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"Estación Calibrada: {soil['zona_label']}",
        ).add_to(fmap)

    # Reference radius (~10 ha visual aid around active station)
    folium.Circle(
        location=[center_lat, center_lon],
        radius=180,
        color="#38bdf8",
        weight=1.5,
        dash_array="5, 5",
        fill=True,
        fill_opacity=0.08,
        tooltip="Área de referencia ~10 ha",
    ).add_to(fmap)

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polygon": {
                "allowIntersection": False,
                "shapeOptions": {"color": "#22c55e", "weight": 3, "fillOpacity": 0.22},
            },
            "rectangle": {
                "shapeOptions": {"color": "#38bdf8", "weight": 3, "fillOpacity": 0.22},
            },
            "polyline": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(fmap)

    folium.LayerControl(position="topright").add_to(fmap)
    return fmap


def build_nasa_evidence_chart(
    location_id: str,
    climatology: dict[str, Any],
    rain_reduction_pct: float,
) -> go.Figure:
    """Create combined Plotly 12-month chart: GPM/IMERG precipitation + MODIS NDVI + stress shading."""
    loc_data = climatology["locations"][location_id]
    months = sorted(loc_data["months"], key=lambda m: m["month"])
    zona_label = loc_data["soil"]["zona_label"]

    x_labels = [m["month_name"][:3] for m in months]
    rain_hist = [m["prectotcorr_mm_mean"] for m in months]
    rain_sim = [round(m["prectotcorr_mm_mean"] * (1.0 - rain_reduction_pct), 2) for m in months]
    ndvi_vals = [m["ndvi_mean"] for m in months]
    stress_freqs = [m["bare_soil_or_stress_freq"] * 100.0 for m in months]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Shade months where bare soil / water stress alerts occur notably
    for idx, m in enumerate(months):
        freq_pct = m["bare_soil_or_stress_freq"] * 100.0
        is_alert_month = (m["bare_soil_or_stress_freq"] >= 0.18) or (m["ndvi_mean"] < 0.25)
        if is_alert_month:
            fig.add_vrect(
                x0=idx - 0.45,
                x1=idx + 0.45,
                fillcolor="rgba(239, 68, 68, 0.18)",
                layer="below",
                line_width=0,
            )

    fig.add_trace(
        go.Bar(
            x=x_labels,
            y=rain_hist,
            name="Lluvia Histórica GPM/IMERG (mm)",
            marker_color="rgba(56, 189, 248, 0.72)",
            hovertemplate="<b>%{x}</b><br>Lluvia histórica: %{y:.1f} mm<extra></extra>",
        ),
        secondary_y=False,
    )

    if rain_reduction_pct > 0.0:
        pct_lbl = int(round(rain_reduction_pct * 100))
        fig.add_trace(
            go.Bar(
                x=x_labels,
                y=rain_sim,
                name=f"Lluvia Simulada (-{pct_lbl}% sequía) (mm)",
                marker_color="rgba(245, 158, 11, 0.85)",
                hovertemplate=f"<b>%{{x}}</b><br>Lluvia -{pct_lbl}%: %{{y:.1f}} mm<extra></extra>",
            ),
            secondary_y=False,
        )

    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=ndvi_vals,
            name="MODIS NDVI Promedio (250m)",
            mode="lines+markers",
            line={"color": "#22c55e", "width": 3},
            marker={"size": 8, "color": "#4ade80", "line": {"width": 1.5, "color": "#052e16"}},
            customdata=stress_freqs,
            hovertemplate=(
                "<b>%{x}</b><br>MODIS NDVI: %{y:.3f}<br>"
                "Frec. alerta suelo desnudo/estrés: %{customdata:.1f}%<extra></extra>"
            ),
        ),
        secondary_y=True,
    )

    fig.add_hline(
        y=0.25,
        line_dash="dot",
        line_color="#ef4444",
        line_width=1.5,
        secondary_y=True,
        annotation_text="Umbral suelo desnudo (NDVI < 0.25)",
        annotation_position="top left",
        annotation_font={"color": "#fca5a5", "size": 11},
    )

    fig.update_layout(
        title={
            "text": f"Evidencia Satelital NASA (2016–2026): Precipitación vs. Vigor Vegetal (MODIS NDVI) — {zona_label}",
            "font": {"color": "#f8fafc", "size": 15},
        },
        barmode="group",
        paper_bgcolor="#121c2e",
        plot_bgcolor="#0b111e",
        font={"color": "#cbd5e1"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 45, "r": 45, "t": 75, "b": 40},
        height=400,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, color="#cbd5e1")
    fig.update_yaxes(
        title_text="Precipitación mensual (mm)",
        secondary_y=False,
        gridcolor="rgba(148, 163, 184, 0.14)",
        color="#7dd3fc",
    )
    fig.update_yaxes(
        title_text="Índice de Vegetación (NDVI)",
        secondary_y=True,
        range=[0.1, 0.72],
        showgrid=False,
        color="#86efac",
    )
    return fig


def _extract_latest_polygon(map_output: dict[str, Any] | None) -> list[list[float]] | None:
    """Extract GeoJSON outer ring [lon, lat] coordinates from folium Draw output."""
    if not map_output:
        return None

    drawing = map_output.get("last_active_drawing")
    if not drawing:
        all_drawings = map_output.get("all_drawings") or []
        if all_drawings:
            drawing = all_drawings[-1]

    if not isinstance(drawing, dict):
        return None
    geometry = drawing.get("geometry") or {}
    if geometry.get("type") != "Polygon":
        return None
    rings = geometry.get("coordinates") or []
    if not rings or len(rings[0]) < 3:
        return None
    return rings[0]


def _init_session_state() -> None:
    defaults = {
        "selected_location_id": "UAAAN_La_Narro",
        "hectares": 10.0,
        "w_water_pct": 33,
        "w_profit_pct": 33,
        "w_nitrogen_pct": 34,
        "rain_reduction_pct_int": 0,
        "last_polygon_hash": None,
        "polygon_notice": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _activate_extreme_drought() -> None:
    st.session_state["rain_reduction_pct_int"] = 20


def _reset_historical_rain() -> None:
    st.session_state["rain_reduction_pct_int"] = 0


def _render_plan_column(col: Any, plan: dict[str, Any], is_recommended: bool) -> None:
    with col:
        card_cls = "plan-card plan-card-recommended" if is_recommended else "plan-card"
        if is_recommended:
            ribbon_html = '<div class="rec-ribbon">★ PLAN RECOMENDADO POR AGROSHIFT</div>'
        elif plan["plan_id"] == "plan_actual":
            ribbon_html = '<div class="baseline-ribbon">Línea Base Histórica</div>'
        else:
            ribbon_html = '<div class="baseline-ribbon">Escenario Alternativo</div>'

        seq_light = plan["semaforo_sequia"]
        hel_light = plan["semaforo_heladas"]
        pla_light = plan["semaforo_plagas"]
        bal = plan["balance_nitrogeno_y_cobertura"]
        comp = plan["component_scores"]

        ahorro_val = plan["ahorro_agua_m3"]
        ahorro_text = f"+{ahorro_val:,.0f} m³ ahorrados" if ahorro_val > 0 else "0 m³ (Referencia)"

        st.markdown(
            f"""
            <div class="{card_cls}">
                {ribbon_html}
                <div class="plan-header">{plan['plan_name']}</div>
                <div class="plan-focus">{plan['strategy_focus']}</div>
                <div class="score-pill">Índice de Idoneidad: {plan['suitability_score']:.1f} / 100</div>
                <div style="font-size:0.75rem;color:#94a3b8;margin-bottom:0.45rem;">
                    Sub-puntajes · Agua: <b>{comp['water_score']:.0f}</b> |
                    Ingreso: <b>{comp['profit_score']:.0f}</b> |
                    N y Suelo: <b>{comp['nitrogen_soil_score']:.0f}</b>
                </div>
                <div class="semaforo-grid">
                    <div class="sem-pill sem-{seq_light}">💧 Sequía<br>{seq_light}</div>
                    <div class="sem-pill sem-{hel_light}">❄️ Heladas<br>{hel_light}</div>
                    <div class="sem-pill sem-{pla_light}">🐛 Plagas<br>{pla_light}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-box-label">Ingreso Neto Estimado (3 años)</div>
                    <div class="metric-box-val">${plan['ingreso_neto_total_mxn']:,.0f} MXN</div>
                </div>
                <div class="metric-box">
                    <div class="metric-box-label">Balance Hídrico vs. Plan Actual</div>
                    <div class="metric-box-val">{ahorro_text}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-box-label">Cobertura y Fijación de Nitrógeno (36 meses)</div>
                    <div class="metric-box-val">
                        {bal['meses_suelo_protegido_3a']}/36 meses protegido ·
                        {bal['meses_suelo_desnudo_3a']} desnudo ·
                        {bal['ciclos_fijacion_nitrogeno_3a']} ciclos N
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        schedule_rows = [
            {
                "Año": f"Año {y['year']}",
                "Primavera-Verano": y["pv_crop_label"],
                "Otoño-Invierno": y["oi_crop_label"],
                "Agua Efec. (mm)": y["effective_water_demand_mm"],
                "Sequía/Plaga": f"{y['drought_light'][0]}/{y['pest_light'][0]}",
            }
            for y in plan["years"]
        ]
        st.dataframe(
            pd.DataFrame(schedule_rows),
            hide_index=True,
            use_container_width=True,
        )

        st.markdown(
            f"""
            <div class="nasa-evidence-box">
                <b>🛰️ Respaldo Científico NASA:</b><br>{plan['nasa_evidence_summary']}
            </div>
            """,
            unsafe_allow_html=True,
        )


def run_smoke_test() -> dict[str, Any]:
    """Automated non-UI verification of datasets, geospatial helpers, engine calls, and figures."""
    climatology, suelos_dict, cultivos_list = _load_reference_data_raw()

    # Test polygon (~10 ha rectangle near UAAAN La Narro)
    sample_poly = [
        [-101.0310, 25.3400],
        [-101.0280, 25.3400],
        [-101.0280, 25.3430],
        [-101.0310, 25.3430],
        [-101.0310, 25.3400],
    ]
    area_ha, c_lat, c_lon = calculate_polygon_area_hectares(sample_poly)
    nearest_id, dist_km = find_nearest_station(c_lat, c_lon, suelos_dict)
    assert area_ha > 0.0
    assert nearest_id == "UAAAN_La_Narro"

    sim_summary = {}
    for loc_id in PLOT_OPTIONS:
        res_normal = simulate_scenarios(loc_id, hectares=area_ha, rain_reduction_pct=0.0)
        res_drought = simulate_scenarios(loc_id, hectares=area_ha, rain_reduction_pct=0.20)
        fig = build_nasa_evidence_chart(loc_id, climatology, rain_reduction_pct=0.20)
        fmap = build_satellite_map(loc_id, suelos_dict)
        assert len(res_normal["plans"]) == 3
        assert len(res_drought["plans"]) == 3
        assert len(fig.data) >= 2
        assert fmap is not None
        sim_summary[loc_id] = {
            "recommended_normal": res_normal["recommended_plan_id"],
            "recommended_drought_20": res_drought["recommended_plan_id"],
        }

    return {
        "locations_verified": len(sim_summary),
        "cultivos_loaded": len(cultivos_list),
        "sample_polygon_ha": area_ha,
        "nearest_station": nearest_id,
        "distance_km": dist_km,
        "simulations": sim_summary,
    }


def main() -> None:
    st.set_page_config(
        page_title="AgroShift | Simulador What-If NASA Coahuila",
        page_icon="🛰️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(DARK_CSS, unsafe_allow_html=True)
    _init_session_state()

    climatology, suelos_dict, cultivos_list = load_reference_data()

    # Sidebar: "Simulador de Vuelo"
    with st.sidebar:
        st.markdown("## 🎛️ Simulador de Vuelo What-If")
        st.caption("Ajusta el tamaño de tu parcela, tus prioridades agronómicas y escenarios de sequía.")

        hectares = st.number_input(
            "📐 Superficie de la parcela (ha)",
            min_value=0.5,
            max_value=5000.0,
            step=0.5,
            key="hectares",
            help="Puedes editar este valor manualmente o dibujar un polígono en el mapa satelital.",
        )

        st.markdown("### 🎯 Prioridades del Agricultor")
        w_water_pct = st.slider(
            "💧 Priorizar ahorro de agua (%)",
            min_value=0,
            max_value=100,
            key="w_water_pct",
        )
        w_profit_pct = st.slider(
            "💰 Maximizar ingresos extra (%)",
            min_value=0,
            max_value=100,
            key="w_profit_pct",
        )
        w_nitrogen_pct = st.slider(
            "🌱 Regenerar nitrógeno y suelo (%)",
            min_value=0,
            max_value=100,
            key="w_nitrogen_pct",
        )

        st.markdown("### 🌦️ Escenario Climático Extremo")
        rain_reduction_pct_int = st.slider(
            "¿Qué pasa si la lluvia cae el próximo año? (%)",
            min_value=0,
            max_value=30,
            step=1,
            format="-%d%%",
            key="rain_reduction_pct_int",
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.button(
                "🔥 Simular Sequía Extrema (-20% lluvia)",
                on_click=_activate_extreme_drought,
                use_container_width=True,
                type="primary",
            )
        with col_btn2:
            st.button(
                "↺ Lluvia Histórica (0%)",
                on_click=_reset_historical_rain,
                use_container_width=True,
            )

    # Top Hero Banner
    st.markdown(
        """
        <div class="agro-hero">
            <div class="agro-badge-nasa">🛰️ NASA Space Apps Challenge · Coahuila</div>
            <div class="agro-title">AgroShift — Simulador de Rotación de Cultivos con Datos Satelitales NASA</div>
            <div class="agro-subtitle">
                Motor de decisiones What-If impulsado por 10 años de datos NASA POWER (MERRA-2 / GPM IMERG),
                MODIS NDVI (250m) y perfiles reales de suelo de Coahuila.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top Bar: Selector de Parcela & Diagnóstico KPI
    col_sel, col_rain_info = st.columns([2, 3])
    with col_sel:
        selected_location_id = st.selectbox(
            "📍 Selecciona una parcela calibrada en Coahuila:",
            options=PLOT_OPTIONS,
            format_func=lambda lid: PLOT_DISPLAY_NAMES.get(lid, lid),
            key="selected_location_id",
        )

    soil = suelos_dict[selected_location_id]
    rain_reduction_pct = rain_reduction_pct_int / 100.0

    # Run simulation engine
    sim_result = simulate_scenarios(
        location_id=selected_location_id,
        hectares=float(hectares),
        weight_water=w_water_pct / 100.0,
        weight_profit=w_profit_pct / 100.0,
        weight_nitrogen=w_nitrogen_pct / 100.0,
        rain_reduction_pct=rain_reduction_pct,
    )

    ctx = sim_result["parcel_context"]
    norm_w = sim_result["normalized_weights"]

    with col_rain_info:
        delta_rain = ctx["annual_simulated_rain_mm"] - ctx["annual_historical_rain_mm"]
        st.info(
            f"**Escenario Activo:** {hectares:.2f} ha · "
            f"Lluvia simulada: **{ctx['annual_simulated_rain_mm']} mm/año** "
            f"({'histórica 10 años' if rain_reduction_pct_int == 0 else f'{delta_rain:.1f} mm / -{rain_reduction_pct_int}%'}) · "
            f"Pesos normalizados → Agua **{norm_w['weight_water']*100:.0f}%** | "
            f"Ingresos **{norm_w['weight_profit']*100:.0f}%** | "
            f"N/Suelo **{norm_w['weight_nitrogen']*100:.0f}%**"
        )

    # Diagnóstico KPI del Suelo
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    kpis = [
        (k1, "Tipo de Suelo", soil["tipo_suelo_label"], f"Municipio: {soil['municipio']}"),
        (k2, "Textura", soil["textura_label"], f"Retención: {soil['retencion_agua']}"),
        (k3, "Elevación Local", f"{soil['local_elevation_m']:.0f} msnm", f"{ctx['annual_frost_days']:.1f} días helada/año"),
        (k4, "Materia Orgánica", f"{soil['materia_organica_pct']:.1f}%", "Indicador fertilidad"),
        (k5, "Pendiente / Erosión", f"{soil['pendiente_pct']:.1f}%", f"Riesgo: {soil['riesgo_erosion']}"),
        (k6, "Lluvia Histórica", f"{ctx['annual_historical_rain_mm']:.1f} mm/año", f"Plaga base: {ctx['annual_pest_risk_days']:.1f} d/año"),
    ]
    for col_box, lbl, val, sub in kpis:
        with col_box:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{lbl}</div>
                    <div class="kpi-value">{val}</div>
                    <div class="kpi-sub">{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div class="problem-banner">
            <b>⚠️ Diagnóstico Agronómico de la Parcela ({soil['zona_label']}):</b> {soil['problema_principal']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("polygon_notice"):
        st.success(st.session_state["polygon_notice"])

    # Interactive Satellite Map with Polygon Draw
    with st.expander("🗺️ Mapa Satelital Interactivo: Dibuja tu Polígono para Calcular Hectáreas y Estación Más Cercana", expanded=True):
        st.caption(
            "Usa la herramienta de polígono o rectángulo en la esquina superior izquierda del mapa para trazar tu terreno. "
            "AgroShift calculará el área geodésica en hectáreas y asignará automáticamente la estación NASA calibrada más cercana."
        )
        fmap = build_satellite_map(selected_location_id, suelos_dict)
        map_output = st_folium(
            fmap,
            height=380,
            use_container_width=True,
            returned_objects=["all_drawings", "last_active_drawing"],
            key=f"agroshift_map_{selected_location_id}",
        )

        drawn_ring = _extract_latest_polygon(map_output)
        if drawn_ring:
            poly_hash = hashlib.md5(json.dumps(drawn_ring, sort_keys=True).encode("utf-8")).hexdigest()
            if poly_hash != st.session_state.get("last_polygon_hash"):
                area_ha, c_lat, c_lon = calculate_polygon_area_hectares(drawn_ring)
                nearest_id, dist_km = find_nearest_station(c_lat, c_lon, suelos_dict)
                st.session_state["last_polygon_hash"] = poly_hash
                st.session_state["hectares"] = area_ha
                st.session_state["selected_location_id"] = nearest_id
                st.session_state["polygon_notice"] = (
                    f"Polígono medido: **{area_ha:.2f} ha** (centroide {c_lat:.4f}, {c_lon:.4f}). "
                    f"Estación calibrada más cercana asignada: **{PLOT_DISPLAY_NAMES[nearest_id]}** (a {dist_km:.2f} km)."
                )
                st.rerun()

    # Main Deliverable: 3 Plans Side-by-Side
    st.markdown(
        '<div class="section-title">📊 Comparativa de Estrategias de Rotación a 3 Años (6 Ciclos: Primavera-Verano + Otoño-Invierno)</div>',
        unsafe_allow_html=True,
    )

    plan_cols = st.columns(3)
    rec_id = sim_result["recommended_plan_id"]
    for col, plan in zip(plan_cols, sim_result["plans"]):
        _render_plan_column(col, plan, is_recommended=(plan["plan_id"] == rec_id))

    # Historical NASA Evidence Chart (Plotly)
    st.markdown(
        '<div class="section-title">📈 Evidencia Histórica Satelital NASA (12 Meses): Lluvia GPM/IMERG vs. MODIS NDVI</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Las franjas sombreadas en rojo señalan meses donde MODIS MOD13Q1 detecta suelo desnudo (NDVI < 0.25) o estrés hídrico recurrente."
    )
    nasa_fig = build_nasa_evidence_chart(selected_location_id, climatology, rain_reduction_pct)
    st.plotly_chart(nasa_fig, use_container_width=True)

    # Crop Catalog Reference
    with st.expander("🌾 Catálogo Agronómico y Económico de Cultivos Calibrados (Coahuila)"):
        crops_df = pd.DataFrame(cultivos_list)[
            [
                "cultivo_label",
                "ciclo_label",
                "consumo_agua_mm",
                "fija_nitrogeno",
                "reduce_erosion",
                "tolerancia_sequia",
                "tolerancia_heladas",
                "rendimiento_ton_ha",
                "precio_ton_mxn",
                "costo_ha_mxn",
                "ingreso_neto_ha_mxn",
            ]
        ].rename(
            columns={
                "cultivo_label": "Cultivo",
                "ciclo_label": "Ciclo",
                "consumo_agua_mm": "Agua (mm)",
                "fija_nitrogeno": "Fija N",
                "reduce_erosion": "Control Erosión",
                "tolerancia_sequia": "Tol. Sequía",
                "tolerancia_heladas": "Tol. Heladas",
                "rendimiento_ton_ha": "Rend. (t/ha)",
                "precio_ton_mxn": "Precio ($/t)",
                "costo_ha_mxn": "Costo ($/ha)",
                "ingreso_neto_ha_mxn": "Ingreso Neto ($/ha)",
            }
        )
        st.dataframe(crops_df, hide_index=True, use_container_width=True)


def _is_running_in_streamlit() -> bool:
    try:
        from streamlit import runtime
        return bool(runtime.exists())
    except Exception:
        return False


if __name__ == "__main__":
    if _is_running_in_streamlit():
        main()
    else:
        print("Ejecuta la aplicación en el navegador con: streamlit run app.py")

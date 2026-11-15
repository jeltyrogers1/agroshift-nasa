import re
from pathlib import Path
import server

# 1. Static DOM ID consistency check between static/index.html and static/app.js
html_text = Path("static/index.html").read_text(encoding="utf-8")
js_text = Path("static/app.js").read_text(encoding="utf-8")
css_text = Path("static/styles.css").read_text(encoding="utf-8")

html_ids = set(re.findall(r'id="([^"]+)"', html_text))
js_ids = set(re.findall(r'\$\("([^"]+)"\)', js_text))
missing_ids = js_ids - html_ids
assert not missing_ids, f"Missing HTML IDs referenced in app.js: {missing_ids}"
print("DOM ID check OK:", len(js_ids), "IDs verified against static/index.html")

# 2. HTML/CSS structural integrity check
assert html_text.strip().endswith("</html>"), "static/index.html does not end with </html>"
assert css_text.count("{") == css_text.count("}"), "Unbalanced braces in static/styles.css"
print(
    "Static assets check OK:",
    f"index.html={len(html_text)}B,",
    f"styles.css={len(css_text)}B ({css_text.count('{')} rules),",
    f"app.js={len(js_text)}B",
)

# 3. FastAPI endpoint verification (/api/init, /api/history/{location_id}, /api/simulate)
init_payload = server.api_init()
assert {"suelos", "cultivos", "climatology", "history_by_location"} <= set(init_payload.keys())
print(
    "GET /api/init OK:",
    "suelos=", len(init_payload["suelos"]),
    "cultivos=", len(init_payload["cultivos"]),
    "history_by_location=", {k: len(v) for k, v in init_payload["history_by_location"].items()},
)

hist_payload = server.api_history("UAAAN_La_Narro")
assert len(hist_payload["series"]) == 130
print(
    "GET /api/history/UAAAN_La_Narro OK:",
    len(hist_payload["series"]),
    "months",
    f"({hist_payload['series'][0]['date_label']} -> {hist_payload['series'][-1]['date_label']})",
)

for test_crop in ["Maiz_Grano", "Alfalfa", "Frijol_Pinto", "Avena_Forrajera"]:
    req = server.SimulateRequest(
        location_id="UAAAN_La_Narro",
        hectares=10.0,
        weight_water=0.33,
        weight_profit=0.33,
        weight_nitrogen=0.34,
        rain_reduction_pct=0.0,
        temp_increase_c=0.0,
        irrigation_mode="temporal",
        market_goal="grano",
        current_crop=test_crop,
    )
    sim_res = server.api_simulate(req)
    print(f"\nPOST /api/simulate (current_crop={test_crop}) — recommended: {sim_res['recommended_plan_id']}")
    for p in sim_res["plans"]:
        assert "consumo_agua_litros" in p and "ahorro_agua_litros" in p and "local_validation_notes" in p
        assert len(p["local_validation_notes"]) == 3
        y1 = p["years"][0]
        assert test_crop in (y1["pv_crop_id"], y1["oi_crop_id"]), f"Year 1 must include {test_crop}: {y1}"
        print(
            f"  - {p['plan_id']} ({p['plan_name']}): "
            f"Y1=({y1['pv_crop_label']} / {y1['oi_crop_label']}), "
            f"consumo={p['consumo_agua_litros']:,.0f} L, "
            f"ahorro={p['ahorro_agua_litros']:,.0f} L, "
            f"utilidad=${p['ingreso_neto_total_mxn']:,.0f} MXN, "
            f"sequia={p['semaforo_sequia']}, plagas={p['semaforo_plagas']}, "
            f"score={p['suitability_score']}"
        )

# 4. Verificación de soil_override (edición manual de suelo en campo)
base_req = server.SimulateRequest(
    location_id="UAAAN_La_Narro",
    hectares=10.0,
    weight_water=0.33,
    weight_profit=0.33,
    weight_nitrogen=0.34,
    current_crop="Maiz_Grano",
    soil_override=None,
)
base_sim = server.api_simulate(base_req)
assert base_sim["is_custom_soil"] is False

custom_req = server.SimulateRequest(
    location_id="UAAAN_La_Narro",
    hectares=10.0,
    weight_water=0.33,
    weight_profit=0.33,
    weight_nitrogen=0.34,
    current_crop="Maiz_Grano",
    soil_override={
        "tipo_suelo_label": "Regosol Calcárico",
        "water_retention_score": 1,
        "textura_label": "Franco Arenoso",
        "erosion_risk_score": 3,
        "materia_organica_pct": 0.7,
        "local_elevation_m": 2250.0,
        "pendiente_pct": 8.0,
    },
)
custom_sim = server.api_simulate(custom_req)
assert custom_sim["is_custom_soil"] is True
assert custom_sim["parcel_context"]["is_custom_soil"] is True
assert custom_sim["parcel_context"]["materia_organica_pct"] == 0.7
assert custom_sim["parcel_context"]["pendiente_pct"] == 8.0
assert "calibrados por el agricultor" in custom_sim["plans"][2]["nasa_evidence_summary"]

base_scores = {p["plan_id"]: p["suitability_score"] for p in base_sim["plans"]}
custom_scores = {p["plan_id"]: p["suitability_score"] for p in custom_sim["plans"]}
print("\nVerificación soil_override (UAAAN_La_Narro: base vs MO=0.7%, pendiente=8.0%, altitud=2250m):")
print("  - Scores base:  ", base_scores)
print("  - Scores custom:", custom_scores)
print("  - Problema suelo recalculado:", custom_sim["parcel_context"]["problema_principal"])
print("  - Evidencia NASA (Plan Regenerativo):", custom_sim["plans"][2]["nasa_evidence_summary"])
assert custom_scores["plan_actual"] < base_scores["plan_actual"], "El Plan Actual debe penalizarse con suelo degradado y pendiente alta"
assert custom_scores["plan_regenerativo"] > custom_scores["plan_actual"], "El Plan Regenerativo debe liderar con urgencia de MO y erosión"

# 5. Verificación del Paso 4 (Manejo y Fertilización: fertilizer_type, tillage_mode, main_concern) y 6 pasos del Wizard
for step_num in range(1, 7):
    assert f'id="step-{step_num}"' in html_text, f"Falta #step-{step_num} en static/index.html"
    assert f'data-goto="{step_num}"' in html_text, f"Falta pill data-goto={step_num} en static/index.html"

sim_quimico = server.api_simulate(
    server.SimulateRequest(
        location_id="UAAAN_La_Narro",
        hectares=10.0,
        current_crop="Maiz_Grano",
        fertilizer_type="quimico",
        tillage_mode="convencional",
        main_concern="suelo",
    )
)
sim_organico = server.api_simulate(
    server.SimulateRequest(
        location_id="UAAAN_La_Narro",
        hectares=10.0,
        current_crop="Maiz_Grano",
        fertilizer_type="organico",
        tillage_mode="conservacion",
        main_concern="sequia",
    )
)
sim_ninguno = server.api_simulate(
    server.SimulateRequest(
        location_id="UAAAN_La_Narro",
        hectares=10.0,
        current_crop="Maiz_Grano",
        fertilizer_type="ninguno",
        tillage_mode="convencional",
        main_concern="suelo",
    )
)

assert "Incluye ahorro estimado en fertilizante nitrogenado" in sim_quimico["plans"][2]["nasa_evidence_summary"]
assert sim_quimico["plans"][2]["ahorro_fertilizante_n_total_mxn"] > sim_organico["plans"][2]["ahorro_fertilizante_n_total_mxn"]
assert sim_organico["plans"][0]["demanda_agua_efectiva_3a_mm"] < sim_quimico["plans"][0]["demanda_agua_efectiva_3a_mm"]
assert sim_ninguno["plans"][0]["ingreso_neto_total_mxn"] < sim_organico["plans"][0]["ingreso_neto_total_mxn"]

print("\nVerificación Paso 4 (Fertilización y Prácticas de Suelo):")
print(
    f"  - Químico + Labranza convencional + Preocupación suelo -> "
    f"Recomendado: {sim_quimico['recommended_plan_id']} ({sim_quimico['recommended_suitability_score']}), "
    f"Ahorro fertilizante N en Plan Regen.: ${sim_quimico['plans'][2]['ahorro_fertilizante_n_total_mxn']:,.0f} MXN"
)
print(
    f"  - Orgánico + Rastrojo conservación + Preocupación sequía -> "
    f"Recomendado: {sim_organico['recommended_plan_id']} ({sim_organico['recommended_suitability_score']}), "
    f"Demanda hídrica Plan Actual: {sim_organico['plans'][0]['demanda_agua_efectiva_3a_mm']} mm (vs {sim_quimico['plans'][0]['demanda_agua_efectiva_3a_mm']} mm)"
)
print("  - Evidencia NASA (Químico, Plan Regenerativo):", sim_quimico["plans"][2]["nasa_evidence_summary"])

# 6. Verificación de Capas Satelitales NASA GIBS WMTS sobre Esri World Imagery en Paso 2
assert "agroOverlayGroup" not in js_text, "No deben quedar halos ni marcadores múltiples en static/app.js"
assert "agro-pill-tooltip" not in js_text, "No deben quedar tooltips flotantes múltiples en static/app.js"
assert "sl-gibs-opacity" not in html_text, "No debe existir slider de opacidad en static/index.html"
assert "World_Imagery" in js_text, "Debe mantenerse Esri.WorldImagery como mapa base nítido"

for token in [
    "MODIS_Terra_CorrectedReflectance_Bands721",
    "2026-10-16",
    "opacity: 0.65",
    "maxNativeZoom: 9",
    "MODIS_Terra_Land_Surface_Temp_Day",
    "2026-05-15",
    "opacity: 0.70",
    "maxNativeZoom: 7",
    "zIndex: 400",
]:
    assert token in js_text, f"Falta token NASA GIBS '{token}' en static/app.js"

for layer_key in ["aerial", "ndvi", "lst"]:
    assert f'data-layer="{layer_key}"' in html_text, f"Falta botón de capa data-layer={layer_key} en static/index.html"

print("Verificación NASA GIBS WMTS OK: Esri WorldImagery + Bandas 7-2-1 (0.65) + LST 2026-05-15 (0.70) con parcela única y leyenda dinámica.")





# Verify hybrid free-text soil override and datalists
from server import api_simulate, SimulateRequest
res_custom_soil = api_simulate(
    SimulateRequest(
        location_id="UAAAN_La_Narro",
        area_ha=5.0,
        drought_offset_pct=-20.0,
        temp_increase_c=1.0,
        irrigation_mode="temporal",
        priority_mode="equilibrado",
        current_crop="Maiz_Grano",
        soil_override={
            "tipo_suelo_label": "Vertisol negro",
            "textura_label": "Arcillo-limoso",
            "materia_organica_pct": 2.2,
            "elevacion_m": 1120.0,
            "pendiente_pct": 4.0,
        },
    )
)
html_check = open("static/index.html", encoding="utf-8").read()
assert 'id="suelos-sugeridos"' not in html_check
assert 'id="texturas-sugeridas"' not in html_check
assert 'data-soil-dropdown="type-text"' in js_text or 'data-soil-dropdown="${fieldKey}"' in js_text
assert "soil-dropdown" in css_text
res_custom_str = str(res_custom_soil)
assert "Vertisol negro" in res_custom_str and "Arcillo-limoso" in res_custom_str
print("CUSTOM_FREE_TEXT_SOIL_OVERRIDE_OK: Vertisol negro / Arcillo-limoso + light-mode custom dropdown verified")


from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
CLIMATOLOGY_PATH = BASE_DIR / "data" / "processed" / "agroshift_climatology_12m.json"
CULTIVOS_PATH = BASE_DIR / "data" / "processed" / "cultivos_coahuila_clean.json"
SUELOS_PATH = BASE_DIR / "data" / "processed" / "suelos_coahuila_clean.json"

PV_MONTHS = {3, 4, 5, 6, 7, 8}
OI_MONTHS = {9, 10, 11, 12, 1, 2}

GRAIN_CROPS = {"Maiz_Grano", "Frijol_Pinto"}
FORAGE_CROPS = {"Avena_Forrajera", "Sorgo_Forrajero", "Cebada_Forrajera", "Alfalfa"}

LIGHT_PHRASE_MAP = {
    "VERDE": "estado VERDE",
    "AMARILLO": "alerta AMARILLA",
    "ROJO": "alerta ROJA",
}

FALLOW_CROP: dict[str, Any] = {
    "cultivo": "Barbecho_Suelo_Desnudo",
    "cultivo_label": "Barbecho (Suelo Desnudo)",
    "tipo_rotacion": "Sin_Cobertura",
    "consumo_agua_mm": 0.0,
    "temp_min_c": -10.0,
    "temp_max_c": 45.0,
    "profundidad_raiz_cm": 0,
    "fija_nitrogeno": "No",
    "fija_nitrogeno_bin": 0,
    "reduce_erosion": "Nula",
    "erosion_control_score": 0,
    "tolerancia_sequia": "Nula",
    "drought_tolerance_score": 0,
    "tolerancia_heladas": "Nula",
    "frost_tolerance_score": 0,
    "ciclo_siembra": "Otono-Invierno",
    "ciclo_label": "Otoño-Invierno",
    "umbral_helada_c": 0.0,
    "rendimiento_ton_ha": 0.0,
    "precio_ton_mxn": 0.0,
    "costo_ha_mxn": 1200.0,  # Rastreo / limpia de maleza en barbecho desnudo
    "ingreso_bruto_ha_mxn": 0.0,
    "ingreso_neto_ha_mxn": -1200.0,
    "profit_score": 0,
}

CUSTOM_CROP_PROFILES: dict[str, dict[str, Any]] = {
    "alto": {
        "tipo_rotacion": "Cultivo_Personalizado_Alto",
        "consumo_agua_mm": 700.0,
        "temp_min_c": 8.0,
        "temp_max_c": 32.0,
        "profundidad_raiz_cm": 90,
        "fija_nitrogeno": "No",
        "fija_nitrogeno_bin": 0,
        "reduce_erosion": "Baja",
        "erosion_control_score": 1,
        "tolerancia_sequia": "Baja",
        "drought_tolerance_score": 1,
        "tolerancia_heladas": "Baja",
        "frost_tolerance_score": 1,
        "ciclo_siembra": "Primavera-Verano",
        "ciclo_label": "Primavera-Verano",
        "umbral_helada_c": 2.0,
        "rendimiento_ton_ha": 18.0,
        "precio_ton_mxn": 6500.0,
        "costo_ha_mxn": 85000.0,
        "ingreso_bruto_ha_mxn": 117000.0,
        "ingreso_neto_ha_mxn": 32000.0,
        "profit_score": 3,
    },
    "medio": {
        "tipo_rotacion": "Cultivo_Personalizado_Medio",
        "consumo_agua_mm": 450.0,
        "temp_min_c": 8.0,
        "temp_max_c": 34.0,
        "profundidad_raiz_cm": 85,
        "fija_nitrogeno": "No",
        "fija_nitrogeno_bin": 0,
        "reduce_erosion": "Media",
        "erosion_control_score": 2,
        "tolerancia_sequia": "Media",
        "drought_tolerance_score": 2,
        "tolerancia_heladas": "Media",
        "frost_tolerance_score": 2,
        "ciclo_siembra": "Primavera-Verano",
        "ciclo_label": "Primavera-Verano",
        "umbral_helada_c": 1.0,
        "rendimiento_ton_ha": 4.0,
        "precio_ton_mxn": 6000.0,
        "costo_ha_mxn": 13000.0,
        "ingreso_bruto_ha_mxn": 24000.0,
        "ingreso_neto_ha_mxn": 11000.0,
        "profit_score": 2,
    },
    "bajo": {
        "tipo_rotacion": "Cultivo_Personalizado_Bajo",
        "consumo_agua_mm": 300.0,
        "temp_min_c": 5.0,
        "temp_max_c": 38.0,
        "profundidad_raiz_cm": 120,
        "fija_nitrogeno": "No",
        "fija_nitrogeno_bin": 0,
        "reduce_erosion": "Alta",
        "erosion_control_score": 3,
        "tolerancia_sequia": "Alta",
        "drought_tolerance_score": 3,
        "tolerancia_heladas": "Media",
        "frost_tolerance_score": 2,
        "ciclo_siembra": "Primavera-Verano",
        "ciclo_label": "Primavera-Verano",
        "umbral_helada_c": 0.5,
        "rendimiento_ton_ha": 16.0,
        "precio_ton_mxn": 1350.0,
        "costo_ha_mxn": 10500.0,
        "ingreso_bruto_ha_mxn": 21600.0,
        "ingreso_neto_ha_mxn": 11100.0,
        "profit_score": 2,
    },
}


def _load_datasets() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    with CLIMATOLOGY_PATH.open("r", encoding="utf-8") as f:
        climatology = json.load(f)
    with CULTIVOS_PATH.open("r", encoding="utf-8") as f:
        cultivos_list = json.load(f)
    with SUELOS_PATH.open("r", encoding="utf-8") as f:
        suelos_list = json.load(f)

    cultivos = {c["cultivo"]: c for c in cultivos_list}
    cultivos["Barbecho_Suelo_Desnudo"] = FALLOW_CROP
    suelos = {s["location_id"]: s for s in suelos_list}
    return climatology, cultivos, suelos


def _normalize_weights(w_water: float, w_profit: float, w_nitrogen: float) -> tuple[float, float, float]:
    w_w = max(0.0, float(w_water))
    w_p = max(0.0, float(w_profit))
    w_n = max(0.0, float(w_nitrogen))
    total = w_w + w_p + w_n
    if total <= 1e-9:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (w_w / total, w_p / total, w_n / total)


def _apply_soil_override(
    base_soil: dict[str, Any],
    soil_override: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool, float]:
    """Combina el perfil edáfico base de la estación con los datos personalizados del agricultor."""
    base_elevation_m = float(base_soil["local_elevation_m"])
    soil = dict(base_soil)
    if not soil_override or not isinstance(soil_override, dict):
        return soil, False, base_elevation_m

    has_changes = False

    if soil_override.get("tipo_suelo_label"):
        soil["tipo_suelo_label"] = str(soil_override["tipo_suelo_label"]).strip()
        has_changes = True

    if soil_override.get("textura_label"):
        soil["textura_label"] = str(soil_override["textura_label"]).strip()
        has_changes = True

    combined_text = f"{soil.get('tipo_suelo_label', '')} {soil.get('textura_label', '')}".lower()

    if soil_override.get("water_retention_score") is not None:
        w_ret = min(3, max(1, int(soil_override["water_retention_score"])))
        soil["water_retention_score"] = w_ret
        soil["retencion_agua"] = {1: "Baja", 2: "Media", 3: "Alta"}[w_ret]
        has_changes = True
    elif has_changes:
        if any(k in combined_text for k in ("aren", "regosol", "pedreg")):
            w_ret = 1
        elif any(k in combined_text for k in ("arcill", "vertisol", "feozem", "negra", "aluvial")):
            w_ret = 3
        else:
            w_ret = int(soil.get("water_retention_score", 2))
        soil["water_retention_score"] = w_ret
        soil["retencion_agua"] = {1: "Baja", 2: "Media", 3: "Alta"}[w_ret]

    if soil_override.get("erosion_risk_score") is not None:
        e_risk = min(3, max(1, int(soil_override["erosion_risk_score"])))
        soil["erosion_risk_score"] = e_risk
        soil["riesgo_erosion"] = {1: "Baja", 2: "Media", 3: "Alta"}[e_risk]
        has_changes = True
    elif has_changes:
        if any(k in combined_text for k in ("limo", "aren", "regosol")):
            e_risk = 3
        elif any(k in combined_text for k in ("arcill", "vertisol")):
            e_risk = 1
        else:
            e_risk = int(soil.get("erosion_risk_score", 2))
        soil["erosion_risk_score"] = e_risk
        soil["riesgo_erosion"] = {1: "Baja", 2: "Media", 3: "Alta"}[e_risk]

    if soil_override.get("materia_organica_pct") is not None:
        mo = round(min(10.0, max(0.1, float(soil_override["materia_organica_pct"]))), 2)
        soil["materia_organica_pct"] = mo
        has_changes = True

    elev_raw = soil_override.get("local_elevation_m", soil_override.get("elevacion_msnm"))
    if elev_raw is not None:
        elev = round(min(3500.0, max(500.0, float(elev_raw))), 1)
        soil["local_elevation_m"] = elev
        soil["elevacion_msnm"] = int(round(elev))
        has_changes = True

    if soil_override.get("pendiente_pct") is not None:
        slope = round(min(30.0, max(0.0, float(soil_override["pendiente_pct"]))), 1)
        soil["pendiente_pct"] = slope
        has_changes = True

    if not has_changes:
        return soil, False, base_elevation_m

    mo_val = float(soil["materia_organica_pct"])
    slope_val = float(soil["pendiente_pct"])
    w_ret_val = int(soil["water_retention_score"])
    e_risk_val = int(soil["erosion_risk_score"])
    elev_m = float(soil["local_elevation_m"])

    soil["needs_nitrogen_fixation"] = 1 if mo_val < 1.5 else 0
    soil["needs_erosion_cover"] = 1 if (slope_val >= 5.0 or e_risk_val >= 3) else 0
    soil["high_drought_vulnerability"] = 1 if (w_ret_val == 1 or mo_val < 1.0) else 0

    alerts: list[str] = []
    if mo_val < 1.5:
        alerts.append(f"Baja materia orgánica ({mo_val}% MO: requiere fijar nitrógeno)")
    if slope_val >= 5.0 or e_risk_val >= 3:
        alerts.append(
            f"Riesgo de erosión por pendiente ({slope_val}%) y textura ({soil['riesgo_erosion'].lower()})"
        )
    if w_ret_val == 1:
        alerts.append("Baja retención hídrica en perfil de suelo")
    if elev_m >= 2000.0:
        alerts.append(f"Exposición térmica a heladas por altitud ({int(round(elev_m))} msnm)")

    soil["problema_principal"] = (
        " · ".join(alerts)
        if alerts
        else "Suelo calibrado en rango favorable de fertilidad, pendiente y retención de humedad"
    )
    return soil, True, base_elevation_m


def _compute_parcel_climate_metrics(
    months_data: list[dict[str, Any]],
    rain_reduction_pct: float,
    temp_increase_c: float = 0.0,
) -> dict[str, float]:
    rain_factor = max(0.0, 1.0 - float(rain_reduction_pct))
    temp_inc = max(0.0, float(temp_increase_c))

    pv_rows = [m for m in months_data if m["month"] in PV_MONTHS]
    oi_rows = [m for m in months_data if m["month"] in OI_MONTHS]

    rain_hist_pv = sum(m["prectotcorr_mm_mean"] for m in pv_rows)
    rain_hist_oi = sum(m["prectotcorr_mm_mean"] for m in oi_rows)
    rain_hist_annual = rain_hist_pv + rain_hist_oi

    rain_adj_pv = rain_hist_pv * rain_factor
    rain_adj_oi = rain_hist_oi * rain_factor
    rain_adj_annual = rain_hist_annual * rain_factor

    soil_moisture_pv = sum(m["soil_moisture_avg_mean"] for m in pv_rows) / len(pv_rows)
    soil_moisture_oi = sum(m["soil_moisture_avg_mean"] for m in oi_rows) / len(oi_rows)
    soil_moisture_annual = sum(m["soil_moisture_avg_mean"] for m in months_data) / len(months_data)

    # Adjust soil moisture under rainfall reduction and heatwave evapotranspiration
    soil_moisture_adj_annual = (
        soil_moisture_annual
        * (1.0 - 0.45 * float(rain_reduction_pct))
        * max(0.75, 1.0 - 0.035 * temp_inc)
    )

    frost_days_pv = sum(m["frost_risk_days_mean"] for m in pv_rows)
    frost_days_oi = sum(m["frost_risk_days_mean"] for m in oi_rows)
    frost_days_annual = frost_days_pv + frost_days_oi

    min_temp_pv = min(m["t2m_min_c_mean"] for m in pv_rows) + temp_inc
    min_temp_oi = min(m["t2m_min_c_mean"] for m in oi_rows) + temp_inc

    pest_days_pv = sum(m["pest_risk_days_mean"] for m in pv_rows)
    pest_days_oi = sum(m["pest_risk_days_mean"] for m in oi_rows)
    pest_days_annual = (pest_days_pv + pest_days_oi) * (1.0 + 0.12 * temp_inc)

    bare_alert_expected_months = sum(m["bare_soil_or_stress_freq"] for m in months_data)
    bare_alert_peak_months = sum(1 for m in months_data if m["bare_soil_or_stress_freq"] >= 0.18)

    return {
        "rain_hist_pv_mm": rain_hist_pv,
        "rain_hist_oi_mm": rain_hist_oi,
        "rain_hist_annual_mm": rain_hist_annual,
        "rain_adj_pv_mm": rain_adj_pv,
        "rain_adj_oi_mm": rain_adj_oi,
        "rain_adj_annual_mm": rain_adj_annual,
        "soil_moisture_pv": soil_moisture_pv,
        "soil_moisture_oi": soil_moisture_oi,
        "soil_moisture_annual": soil_moisture_annual,
        "soil_moisture_adj_annual": soil_moisture_adj_annual,
        "frost_days_pv": frost_days_pv,
        "frost_days_oi": frost_days_oi,
        "frost_days_annual": frost_days_annual,
        "min_temp_pv_c": min_temp_pv,
        "min_temp_oi_c": min_temp_oi,
        "pest_days_pv": pest_days_pv,
        "pest_days_oi": pest_days_oi,
        "pest_days_annual": pest_days_annual,
        "bare_alert_expected_months_yr": bare_alert_expected_months,
        "bare_alert_peak_months_yr": float(bare_alert_peak_months),
    }


def _build_rotation_templates(
    location_id: str,
    current_crop: str,
    cultivos: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Construye los 3 planes comparativos a 3 años (6 ciclos) adaptados a la parcela
    y anclados al cultivo actual o requerido (`current_crop`) del agricultor.
    """
    is_high_altitude = location_id == "Los_Lirios_Arteaga"
    is_hyper_arid = location_id == "General_Cepeda"

    crop_info = cultivos[current_crop]
    crop_label = crop_info["cultivo_label"]
    ciclo = crop_info["ciclo_siembra"]

    # 1. Plan Actual (Línea Base del Agricultor: monocultivo de current_crop durante 3 años)
    if ciclo == "Todo_el_ano":
        actual_years = [
            {"year": 1, "pv": current_crop, "oi": current_crop},
            {"year": 2, "pv": current_crop, "oi": current_crop},
            {"year": 3, "pv": current_crop, "oi": current_crop},
        ]
        actual_focus = f"Monocultivo continuo de {crop_label} (Todo el año) durante los 3 años"
    elif ciclo == "Otono-Invierno":
        actual_years = [
            {"year": 1, "pv": "Barbecho_Suelo_Desnudo", "oi": current_crop},
            {"year": 2, "pv": "Barbecho_Suelo_Desnudo", "oi": current_crop},
            {"year": 3, "pv": "Barbecho_Suelo_Desnudo", "oi": current_crop},
        ]
        actual_focus = f"Monocultivo de {crop_label} en Otoño-Invierno con suelo desnudo en Primavera-Verano"
    else:
        actual_years = [
            {"year": 1, "pv": current_crop, "oi": "Barbecho_Suelo_Desnudo"},
            {"year": 2, "pv": current_crop, "oi": "Barbecho_Suelo_Desnudo"},
            {"year": 3, "pv": current_crop, "oi": "Barbecho_Suelo_Desnudo"},
        ]
        actual_focus = f"Monocultivo de {crop_label} en Primavera-Verano con suelo desnudo en Otoño-Invierno"

    plan_actual = {
        "plan_id": "plan_actual",
        "plan_name": f"Plan Actual (Monocultivo: {crop_label})",
        "strategy_focus": actual_focus,
        "years": actual_years,
    }

    # Coberturas invernales de bajo consumo adaptadas a la altitud de la parcela
    winter_cover_primary = "Cebada_Forrajera" if is_high_altitude else "Avena_Forrajera"
    winter_cover_alt = "Avena_Forrajera" if is_high_altitude else "Cebada_Forrajera"

    # 2. Plan Conservación Hídrica (Mantiene current_crop en Año 1 y rota en Años 2 y 3 hacia mínimo consumo hídrico)
    if ciclo == "Todo_el_ano":
        cons_y1 = {"year": 1, "pv": current_crop, "oi": current_crop}
    elif ciclo == "Otono-Invierno":
        cons_y1 = {"year": 1, "pv": "Sorgo_Forrajero", "oi": current_crop}
    else:
        cons_y1 = {"year": 1, "pv": current_crop, "oi": winter_cover_primary}

    if cons_y1["pv"] == "Sorgo_Forrajero":
        cons_y2 = {"year": 2, "pv": "Frijol_Pinto", "oi": "Cebada_Forrajera"}
        cons_y3 = {"year": 3, "pv": "Sorgo_Forrajero", "oi": winter_cover_primary}
    elif cons_y1["pv"] == "Frijol_Pinto":
        cons_y2 = {"year": 2, "pv": "Sorgo_Forrajero", "oi": "Cebada_Forrajera"}
        cons_y3 = {"year": 3, "pv": "Frijol_Pinto", "oi": "Cebada_Forrajera"}
    else:
        cons_y2 = {"year": 2, "pv": "Sorgo_Forrajero", "oi": "Cebada_Forrajera"}
        cons_y3 = {"year": 3, "pv": "Frijol_Pinto", "oi": winter_cover_primary}

    plan_conservacion = {
        "plan_id": "plan_conservacion_hidrica",
        "plan_name": "Plan Conservación Hídrica",
        "strategy_focus": f"Año 1 con {crop_label} y rotación en Años 2–3 hacia cultivos de baja demanda hídrica y cobertura invernal",
        "years": [cons_y1, cons_y2, cons_y3],
    }

    # 3. Plan Regenerativo (Mantiene current_crop en Año 1 y alterna en Años 2 y 3 con leguminosas y cobertura continua)
    if ciclo == "Todo_el_ano":
        reg_y1 = {"year": 1, "pv": current_crop, "oi": current_crop}
        reg_y2 = {
            "year": 2,
            "pv": "Sorgo_Forrajero" if is_hyper_arid else "Maiz_Grano",
            "oi": winter_cover_primary,
        }
        reg_y3 = {"year": 3, "pv": "Frijol_Pinto", "oi": winter_cover_alt}
    elif ciclo == "Otono-Invierno":
        reg_y1 = {"year": 1, "pv": "Frijol_Pinto", "oi": current_crop}
        reg_y2 = {
            "year": 2,
            "pv": "Sorgo_Forrajero",
            "oi": winter_cover_alt,
        }
        reg_y3 = {"year": 3, "pv": "Frijol_Pinto", "oi": winter_cover_primary}
    elif current_crop == "Frijol_Pinto":
        reg_y1 = {"year": 1, "pv": "Frijol_Pinto", "oi": winter_cover_primary}
        reg_y2 = {
            "year": 2,
            "pv": "Sorgo_Forrajero" if is_hyper_arid else "Maiz_Grano",
            "oi": winter_cover_alt,
        }
        reg_y3 = {"year": 3, "pv": "Frijol_Pinto", "oi": winter_cover_primary}
    elif current_crop == "Sorgo_Forrajero":
        reg_y1 = {"year": 1, "pv": "Sorgo_Forrajero", "oi": winter_cover_primary}
        reg_y2 = {"year": 2, "pv": "Frijol_Pinto", "oi": winter_cover_alt}
        reg_y3 = {
            "year": 3,
            "pv": "Frijol_Pinto" if is_hyper_arid else "Maiz_Grano",
            "oi": winter_cover_primary,
        }
    else:  # Maiz_Grano o cultivo personalizado Primavera-Verano
        reg_y1 = {"year": 1, "pv": current_crop, "oi": winter_cover_primary}
        reg_y2 = {"year": 2, "pv": "Frijol_Pinto", "oi": winter_cover_alt}
        if is_hyper_arid:
            reg_y3 = {"year": 3, "pv": "Sorgo_Forrajero", "oi": winter_cover_primary}
        else:
            reg_y3 = {"year": 3, "pv": "Alfalfa", "oi": "Alfalfa"}

    plan_regenerativo = {
        "plan_id": "plan_regenerativo",
        "plan_name": "Plan Regenerativo (Nitrógeno y Cobertura)",
        "strategy_focus": f"Año 1 con {crop_label} y alternancia en Años 2–3 con leguminosas fijadoras de nitrógeno y cobertura viva",
        "years": [reg_y1, reg_y2, reg_y3],
    }

    return [plan_actual, plan_conservacion, plan_regenerativo]


def _evaluate_year(
    year_spec: dict[str, Any],
    prev_pv_crop: str | None,
    consecutive_monoculture_years: int,
    cumulative_n_fixed_cycles: int,
    cultivos: dict[str, dict[str, Any]],
    soil: dict[str, Any],
    climate: dict[str, float],
    rain_reduction_pct: float,
    temp_increase_c: float = 0.0,
    irrigation_mode: str = "temporal",
    base_elevation_m: float | None = None,
    is_custom_soil: bool = False,
    fertilizer_type: str = "quimico",
    tillage_mode: str = "convencional",
    is_baseline_plan: bool = False,
) -> dict[str, Any]:
    pv_id = year_spec["pv"]
    oi_id = year_spec["oi"]
    pv_crop = cultivos[pv_id]
    oi_crop = cultivos[oi_id]
    is_perennial_alfalfa = pv_id == "Alfalfa" and oi_id == "Alfalfa"
    has_summer_cover = pv_id != "Barbecho_Suelo_Desnudo"
    has_winter_cover = oi_id != "Barbecho_Suelo_Desnudo"
    has_full_year_cover = has_summer_cover and has_winter_cover

    # Cada +1.0 °C incrementa la demanda hídrica de los cultivos en ~6%
    heat_water_factor = 1.0 + 0.06 * float(temp_increase_c)

    # 1. Cálculo de demanda hídrica efectiva (mm/ha)
    if is_perennial_alfalfa:
        pv_water_raw = pv_crop["consumo_agua_mm"] * 0.60 * heat_water_factor
        oi_water_raw = oi_crop["consumo_agua_mm"] * 0.40 * heat_water_factor
    else:
        pv_water_raw = float(pv_crop["consumo_agua_mm"]) * heat_water_factor
        oi_water_raw = float(oi_crop["consumo_agua_mm"]) * heat_water_factor

    water_ret_score = int(soil["water_retention_score"])  # 1 a 3
    tillage_evap_mult = 0.84 if tillage_mode == "conservacion" else 1.0
    winter_bare_evap_loss_mm = (
        {1: 195.0, 2: 165.0, 3: 135.0}.get(water_ret_score, 160.0) * heat_water_factor * tillage_evap_mult
    )
    summer_bare_evap_loss_mm = (
        {1: 315.0, 2: 275.0, 3: 235.0}.get(water_ret_score, 275.0) * heat_water_factor * tillage_evap_mult
    )

    # Penalización por compactación y escorrentía cuando se repite un monocultivo año tras año
    monoculture_runoff_loss_mm = 22.0 * consecutive_monoculture_years * heat_water_factor
    if is_custom_soil and not has_full_year_cover:
        # En suelos con mayor pendiente personalizada, dejar el suelo desnudo incrementa pérdida por escorrentía
        monoculture_runoff_loss_mm += max(0.0, float(soil["pendiente_pct"]) - 3.5) * 6.0
    if tillage_mode == "convencional" and int(soil["erosion_risk_score"]) >= 3 and not has_full_year_cover:
        monoculture_runoff_loss_mm += 18.0 * heat_water_factor

    tillage_mulch_bonus_mm = 22.0 if tillage_mode == "conservacion" else 0.0

    if is_perennial_alfalfa:
        # La alfalfa perenne mantiene transpiración activa todo el año; exige la lámina más alta del catálogo
        perennial_evap_surcharge_mm = {1: 115.0, 2: 95.0, 3: 75.0}.get(water_ret_score, 95.0) * heat_water_factor
        winter_rain_captured_mm = min(oi_water_raw * 0.45, climate["rain_adj_oi_mm"] * 0.70)
        mulch_moisture_credit_mm = tillage_mulch_bonus_mm * 0.5
        effective_water_demand_mm = (
            pv_water_raw
            + oi_water_raw
            + perennial_evap_surcharge_mm
            - winter_rain_captured_mm
            - mulch_moisture_credit_mm
            + monoculture_runoff_loss_mm
        )
    elif has_full_year_cover:
        winter_rain_captured_mm = min(oi_water_raw * 0.72, climate["rain_adj_oi_mm"] * 0.85)
        mulch_moisture_credit_mm = 45.0 + 12.0 * water_ret_score + tillage_mulch_bonus_mm
        effective_water_demand_mm = (
            pv_water_raw
            + (oi_water_raw - winter_rain_captured_mm - mulch_moisture_credit_mm)
            + monoculture_runoff_loss_mm
        )
    elif has_summer_cover and not has_winter_cover:
        effective_water_demand_mm = (
            pv_water_raw + winter_bare_evap_loss_mm - tillage_mulch_bonus_mm * 0.6 + monoculture_runoff_loss_mm
        )
    else:
        # Cultivo solo en Otoño-Invierno con suelo desnudo en Primavera-Verano
        winter_rain_captured_mm = min(oi_water_raw * 0.50, climate["rain_adj_oi_mm"] * 0.65)
        effective_water_demand_mm = (
            summer_bare_evap_loss_mm
            + (oi_water_raw - winter_rain_captured_mm - tillage_mulch_bonus_mm * 0.6)
            + monoculture_runoff_loss_mm
        )

    # 2. Semáforo de Sequía
    mo_buffer_adj = (float(soil["materia_organica_pct"]) - 1.5) * 18.0 if is_custom_soil else 0.0
    org_fert_buffer_mm = 26.0 if fertilizer_type == "organico" else (12.0 if fertilizer_type == "mixto" else 0.0)
    tillage_buffer_mm = 24.0 if tillage_mode == "conservacion" else 0.0
    soil_buffer_mm = (
        climate["soil_moisture_adj_annual"] * (590.0 + 135.0 * water_ret_score + mo_buffer_adj)
        + org_fert_buffer_mm
        + tillage_buffer_mm
    )
    irrigation_supply_bonus_mm = 135.0 if irrigation_mode == "riego" else 0.0
    available_water_supply_mm = climate["rain_adj_annual_mm"] + soil_buffer_mm + irrigation_supply_bonus_mm

    if has_full_year_cover:
        avg_drought_tol = float(pv_crop["drought_tolerance_score"]) * 0.65 + float(oi_crop["drought_tolerance_score"]) * 0.35
    elif has_summer_cover:
        avg_drought_tol = float(pv_crop["drought_tolerance_score"])
    else:
        avg_drought_tol = float(oi_crop["drought_tolerance_score"])

    drought_vulnerability_penalty = 10.0 if int(soil["high_drought_vulnerability"]) == 1 else 0.0
    if tillage_mode == "convencional" and int(soil["erosion_risk_score"]) >= 3:
        drought_vulnerability_penalty += 5.5
    elif tillage_mode == "conservacion":
        drought_vulnerability_penalty -= 3.5

    monoculture_compaction_penalty = 2.5 * consecutive_monoculture_years
    heat_stress_penalty = 4.5 * float(temp_increase_c)

    # En modalidad temporal, cultivos de alta demanda (Maíz 550 mm, Alfalfa 750 mm) sufren mayor estrés
    high_demand_temporal_penalty = 0.0
    primary_water_mm = float(pv_crop["consumo_agua_mm"]) if has_summer_cover else float(oi_crop["consumo_agua_mm"])
    if irrigation_mode == "temporal" and primary_water_mm >= 500.0:
        if is_perennial_alfalfa:
            high_demand_temporal_penalty = 12.0 + 6.0 * (rain_reduction_pct / 0.20 + temp_increase_c * 0.5)
        elif rain_reduction_pct > 0.0 or temp_increase_c > 0.0:
            high_demand_temporal_penalty = 6.0 * (rain_reduction_pct / 0.20 + temp_increase_c * 0.5)

    drought_stress_index = (
        (effective_water_demand_mm / max(200.0, available_water_supply_mm)) * 100.0
        - (avg_drought_tol - 2.0) * 14.0
        + drought_vulnerability_penalty
        + monoculture_compaction_penalty
        + heat_stress_penalty
        + high_demand_temporal_penalty
    )

    if drought_stress_index >= 106.0:
        drought_light = "ROJO"
    elif drought_stress_index >= 84.0:
        drought_light = "AMARILLO"
    else:
        drought_light = "VERDE"

    # 3. Semáforo de Heladas (ajustando exposición térmica según altitud local personalizada)
    elev_m = float(soil["local_elevation_m"])
    high_elevation_frost_exposure = 1.0 if elev_m >= 2000.0 else 0.0
    pv_frost_tol = int(pv_crop["frost_tolerance_score"]) if has_summer_cover else 1
    oi_frost_tol = int(oi_crop["frost_tolerance_score"]) if has_winter_cover else 1

    elev_diff_m = (elev_m - float(base_elevation_m)) if (is_custom_soil and base_elevation_m is not None) else 0.0
    elevation_frost_delta = (elev_diff_m / 100.0) * (3.5 if not has_winter_cover else max(1.2, (4.5 - oi_frost_tol) * 1.1))

    frost_risk_score = max(
        0.0,
        climate["frost_days_oi"] * (3.6 - 0.78 * oi_frost_tol)
        + climate["frost_days_pv"] * (7.0 - 1.4 * pv_frost_tol)
        + high_elevation_frost_exposure * (14.0 if not has_winter_cover else max(0.0, (4 - oi_frost_tol) * 4.5))
        + max(0.0, float(oi_crop["umbral_helada_c"]) - (climate["min_temp_oi_c"] - 4.0)) * 2.5
        - 2.5 * float(temp_increase_c)
        + elevation_frost_delta,
    )

    if frost_risk_score >= 38.0:
        frost_light = "ROJO"
    elif frost_risk_score >= 22.0:
        frost_light = "AMARILLO"
    else:
        frost_light = "VERDE"

    # 4. Semáforo de Plagas (con penalización explícita por monocultivo: +35% Año 2, +70% Año 3)
    if consecutive_monoculture_years == 0:
        is_legume_rotation = int(pv_crop["fija_nitrogeno_bin"]) == 1 or int(oi_crop["fija_nitrogeno_bin"]) == 1
        pest_multiplier = (
            0.62
            if (has_full_year_cover and is_legume_rotation)
            else (0.70 if has_full_year_cover else 1.00)
        )
    elif consecutive_monoculture_years == 1:
        pest_multiplier = 1.35
    else:
        pest_multiplier = 1.70

    effective_pest_days = climate["pest_days_annual"] * pest_multiplier
    if effective_pest_days >= 45.0:
        pest_light = "ROJO"
    elif effective_pest_days >= 30.0:
        pest_light = "AMARILLO"
    else:
        pest_light = "VERDE"

    # 5. Ingreso neto por hectárea ajustado por riesgo climático, modalidad hídrica y ahorro de fertilizante N
    if is_perennial_alfalfa:
        base_net_income_ha = float(pv_crop["ingreso_neto_ha_mxn"])
    else:
        base_net_income_ha = float(pv_crop["ingreso_neto_ha_mxn"]) + float(oi_crop["ingreso_neto_ha_mxn"])

    n_fixing_cycles_this_year = int(pv_crop["fija_nitrogeno_bin"]) + (
        int(oi_crop["fija_nitrogeno_bin"]) if not is_perennial_alfalfa else 0
    )
    has_carryover_n = cumulative_n_fixed_cycles > 0 and has_summer_cover and int(pv_crop["fija_nitrogeno_bin"]) == 0

    # Costo extra por dependencia de fertilizante sintético en monocultivo y bono de ahorro al rotar con leguminosas
    synthetic_monoculture_cost_ha = 0.0
    if fertilizer_type == "quimico":
        if is_baseline_plan and (n_fixing_cycles_this_year == 0 or consecutive_monoculture_years > 0):
            synthetic_monoculture_cost_ha = 1600.0 + 900.0 * consecutive_monoculture_years
        nitrogen_fertilizer_savings_ha = (
            (3200.0 * n_fixing_cycles_this_year if not is_baseline_plan else 0.0)
            + (2600.0 if has_carryover_n else 0.0)
        )
    elif fertilizer_type == "mixto":
        if is_baseline_plan and consecutive_monoculture_years > 0:
            synthetic_monoculture_cost_ha = 750.0 * consecutive_monoculture_years
        nitrogen_fertilizer_savings_ha = (
            (2100.0 * n_fixing_cycles_this_year if not is_baseline_plan else 0.0)
            + (1800.0 if has_carryover_n else 0.0)
        )
    elif fertilizer_type == "organico":
        nitrogen_fertilizer_savings_ha = (
            (1400.0 * n_fixing_cycles_this_year if not is_baseline_plan else 0.0)
            + (1500.0 if has_carryover_n else 0.0)
        )
    else:  # "ninguno"
        nitrogen_fertilizer_savings_ha = (
            (2200.0 * n_fixing_cycles_this_year if not is_baseline_plan else 0.0)
            + (1900.0 if has_carryover_n else 0.0)
        )

    # Si no se fertiliza ("ninguno") y el suelo tiene MO < 1.5%, penalizar rendimiento del Plan Actual por agotamiento
    nutrient_exhaustion_mult = 1.0
    if fertilizer_type == "ninguno" and float(soil["materia_organica_pct"]) < 1.5 and is_baseline_plan:
        nutrient_exhaustion_mult = max(0.76, 0.90 - 0.05 * consecutive_monoculture_years)

    if irrigation_mode == "riego":
        drought_mult = {"VERDE": 1.00, "AMARILLO": 0.94, "ROJO": 0.82}[drought_light]
    else:
        drought_mult = {"VERDE": 1.00, "AMARILLO": 0.88, "ROJO": 0.68}[drought_light]

    continuous_water_factor = max(0.75, min(1.03, 1.0 - max(0.0, drought_stress_index - 65.0) * 0.0025))
    frost_mult = {"VERDE": 1.00, "AMARILLO": 0.93, "ROJO": 0.78}[frost_light]
    pest_mult = {"VERDE": 1.00, "AMARILLO": 0.94, "ROJO": 0.82}[pest_light]

    combined_yield_factor = (
        drought_mult * continuous_water_factor * frost_mult * pest_mult * nutrient_exhaustion_mult
    )
    adjusted_net_income_ha = (
        (base_net_income_ha * combined_yield_factor)
        + nitrogen_fertilizer_savings_ha
        - synthetic_monoculture_cost_ha
    )

    months_covered = (6 if has_summer_cover else 0) + (6 if has_winter_cover else 0)
    months_bare = 12 - months_covered

    return {
        "year": int(year_spec["year"]),
        "pv_crop_id": pv_id,
        "pv_crop_label": pv_crop["cultivo_label"],
        "oi_crop_id": oi_id,
        "oi_crop_label": oi_crop["cultivo_label"],
        "catalog_water_mm": round(pv_water_raw + oi_water_raw, 1),
        "effective_water_demand_mm": round(effective_water_demand_mm, 1),
        "drought_stress_index": round(drought_stress_index, 1),
        "drought_light": drought_light,
        "frost_risk_score": round(frost_risk_score, 1),
        "frost_light": frost_light,
        "pest_multiplier": round(pest_multiplier, 2),
        "effective_pest_days": round(effective_pest_days, 1),
        "pest_light": pest_light,
        "base_net_income_ha_mxn": round(base_net_income_ha, 2),
        "adjusted_net_income_ha_mxn": round(adjusted_net_income_ha, 2),
        "nitrogen_fertilizer_savings_ha_mxn": round(nitrogen_fertilizer_savings_ha, 2),
        "months_soil_covered": months_covered,
        "months_bare_soil": months_bare,
        "n_fixing_cycles": n_fixing_cycles_this_year,
    }


def _aggregate_light(lights: list[str]) -> str:
    if "ROJO" in lights:
        return "ROJO"
    if "AMARILLO" in lights:
        return "AMARILLO"
    return "VERDE"


def _build_local_validation_notes(
    plan_metrics: dict[str, Any],
    soil: dict[str, Any],
    irrigation_mode: str,
    market_goal: str,
    current_crop_label: str,
) -> list[str]:
    municipio = soil["municipio"].replace("_", " ")
    tipo_suelo = soil["tipo_suelo_label"]
    pendiente = soil["pendiente_pct"]
    irrig_label = "temporal (secano)" if irrigation_mode == "temporal" else "riego de auxilio"
    goal_label = "grano comercial" if market_goal == "grano" else "forraje ganadero"

    crops_used = sorted(
        {
            y["pv_crop_label"]
            for y in plan_metrics["years"]
            if y["pv_crop_id"] != "Barbecho_Suelo_Desnudo"
        }
        | {
            y["oi_crop_label"]
            for y in plan_metrics["years"]
            if y["oi_crop_id"] != "Barbecho_Suelo_Desnudo"
        }
    )
    crops_str = ", ".join(crops_used)

    return [
        (
            f"Resolución espacial: Las celdas climáticas NASA POWER (MERRA-2, ~50 km) y píxeles MODIS NDVI (250 m) "
            f"no capturan microclimas ni escorrentías locales; verifique en campo la pendiente real ({pendiente}%) "
            f"y zonas bajas propensas a helada dentro de su predio en {municipio}."
        ),
        (
            f"Validación de suelo y agua para {current_crop_label}: Confirme mediante análisis de laboratorio el pH, "
            f"carbonatos activos y salinidad de su {tipo_suelo}, así como la disponibilidad efectiva de lámina en modalidad de {irrig_label}."
        ),
        (
            f"Validación comercial y agronómica: Verifique abasto local de semilla certificada para {crops_str} "
            f"y precios/contratos de compra orientados a {goal_label} en el corredor {municipio} – Saltillo."
        ),
    ]


def _build_nasa_evidence_summary(
    plan_id: str,
    plan_name: str,
    current_crop_info: dict[str, Any],
    soil: dict[str, Any],
    climate: dict[str, float],
    rain_reduction_pct: float,
    temp_increase_c: float,
    hectares: float,
    plan_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    is_custom_soil: bool = False,
    fertilizer_type: str = "quimico",
) -> str:
    zona = soil["zona_label"]
    current_crop_label = current_crop_info["cultivo_label"]
    current_ciclo = current_crop_info["ciclo_siembra"]
    rain_hist = climate["rain_hist_annual_mm"]
    rain_adj = climate["rain_adj_annual_mm"]
    modis_alert_months = max(1, round(climate["bare_alert_expected_months_yr"]))
    modis_alert_3y = modis_alert_months * 3

    soil_calib_clause = (
        f", utilizando datos de suelo calibrados por el agricultor "
        f"({soil['tipo_suelo_label']}, {soil['textura_label']}, {soil['materia_organica_pct']}% MO, "
        f"pendiente {soil['pendiente_pct']}% y {int(round(soil['local_elevation_m']))} msnm)"
        if is_custom_soil
        else ""
    )

    rain_clause = (
        f"bajo una sequía simulada de -{int(round(rain_reduction_pct * 100))}% "
        f"(lluvia efectiva de {rain_adj:.1f} mm/año frente a {rain_hist:.1f} mm históricos)"
        if rain_reduction_pct > 0
        else f"con una precipitación histórica de {rain_hist:.1f} mm/año"
    )
    if temp_increase_c > 0:
        rain_clause += f" y un aumento térmico de +{temp_increase_c:.1f} °C"
    rain_clause += soil_calib_clause

    plan_seq_phrase = LIGHT_PHRASE_MAP[plan_metrics["semaforo_sequia"]]
    base_seq_phrase = LIGHT_PHRASE_MAP[baseline_metrics["semaforo_sequia"]]
    base_pla_phrase = LIGHT_PHRASE_MAP[baseline_metrics["semaforo_plagas"]]

    if plan_id == "plan_actual":
        fert_warn = ""
        if fertilizer_type == "quimico":
            fert_warn = " e incrementa el gasto anual por dependencia de fertilizante químico sintético (Urea/DAP)"
        elif fertilizer_type == "ninguno" and float(soil["materia_organica_pct"]) < 1.5:
            fert_warn = " y reduce el rendimiento por agotamiento de nutrientes sin fertilización"
        if current_ciclo == "Todo_el_ano":
            return (
                f"Con base en 10 años de datos NASA POWER (MERRA-2/IMERG) y MODIS MOD13Q1 en {zona}, "
                f"{rain_clause}, mantener {current_crop_label} en monocultivo continuo durante 3 años en {hectares:.1f} ha "
                f"demanda {plan_metrics['consumo_agua_total_3a_m3']:,.0f} m³ de agua ({plan_metrics['consumo_agua_litros']:,} L), "
                f"eleva +70% la presión de plagas hacia el Año 3 ({plan_metrics['years'][2]['effective_pest_days']:.1f} días equivalentes){fert_warn} "
                f"y coloca el diagnóstico de sequía en {plan_seq_phrase}."
            )
        return (
            f"Con base en 10 años de datos NASA POWER (MERRA-2/IMERG) y MODIS MOD13Q1 en {zona}, "
            f"{rain_clause}, el monocultivo continuo de {current_crop_label} deja el suelo desnudo 18 meses en 3 años "
            f"(exponiendo la parcela en los {modis_alert_months} meses críticos/año de baja cobertura detectados por MODIS NDVI), "
            f"eleva +70% la presión de plagas hacia el Año 3 ({plan_metrics['years'][2]['effective_pest_days']:.1f} días equivalentes){fert_warn} "
            f"y coloca el diagnóstico de sequía en {plan_seq_phrase}."
        )

    water_saved = plan_metrics["ahorro_agua_m3"]
    income_diff = plan_metrics["ingreso_neto_total_mxn"] - baseline_metrics["ingreso_neto_total_mxn"]
    pv_crops_used = sorted(
        {y["pv_crop_label"] for y in plan_metrics["years"] if y["pv_crop_id"] != "Barbecho_Suelo_Desnudo"}
    )
    oi_crops_used = sorted(
        {y["oi_crop_label"] for y in plan_metrics["years"] if y["oi_crop_id"] != "Barbecho_Suelo_Desnudo"}
    )
    crops_str = ", ".join(pv_crops_used + [c for c in oi_crops_used if c not in pv_crops_used])

    if water_saved >= 0:
        water_clause = f"ahorra {water_saved:,.0f} m³ de agua en 3 años"
    else:
        water_clause = f"requiere {abs(water_saved):,.0f} m³ adicionales para sostener cobertura perenne fijadora de nitrógeno"

    n_savings_total = float(plan_metrics.get("ahorro_fertilizante_n_total_mxn", 0.0))
    fert_savings_clause = ""
    if fertilizer_type == "quimico" and n_savings_total > 0:
        fert_savings_clause = (
            f" Incluye ahorro estimado en fertilizante nitrogenado (${n_savings_total:,.0f} MXN en 3 años) al rotar con leguminosas."
        )
    elif fertilizer_type == "mixto" and n_savings_total > 0:
        fert_savings_clause = (
            f" Incluye ahorro estimado en fertilizante nitrogenado (${n_savings_total:,.0f} MXN) al incorporar leguminosas."
        )

    return (
        f"Con base en 10 años de registros satelitales NASA POWER y MODIS NDVI en {zona}, "
        f"{rain_clause}, mientras el monocultivo de {current_crop_label} entra en {base_seq_phrase} de sequía "
        f"y {base_pla_phrase} de plagas, sembrar {current_crop_label} en el Año 1 y rotar con {crops_str} en {hectares:.1f} ha "
        f"{water_clause}, protege el suelo los 36 meses "
        f"(mitigando {modis_alert_3y} meses acumulados de alerta por suelo desnudo/estrés en MODIS NDVI) "
        f"y genera ${plan_metrics['ingreso_neto_total_mxn']:,.0f} MXN netos "
        f"({'+' if income_diff >= 0 else ''}${income_diff:,.0f} MXN vs. monocultivo de {current_crop_label}).{fert_savings_clause}"
    )


FERTILIZER_LABELS = {
    "quimico": "Fertilizante Químico (Urea / DAP)",
    "mixto": "Mixto (Químico + Abono Orgánico)",
    "organico": "Orgánico / Composta / Biofertilizante",
    "ninguno": "Sin fertilización",
}

TILLAGE_LABELS = {
    "convencional": "Labranza tradicional / Suelo limpio",
    "conservacion": "Dejar rastrojo como cobertura",
}

CONCERN_LABELS = {
    "sequia": "Falta de lluvia / sequía",
    "suelo": "Tierra cansada / baja fertilidad",
    "plagas": "Plagas frecuentes",
    "heladas": "Heladas tempranas",
}


def simulate_scenarios(
    location_id: str,
    hectares: float = 10.0,
    weight_water: float = 0.33,
    weight_profit: float = 0.33,
    weight_nitrogen: float = 0.34,
    rain_reduction_pct: float = 0.0,
    temp_increase_c: float = 0.0,
    irrigation_mode: str = "temporal",
    market_goal: str = "grano",
    current_crop: str = "Maiz_Grano",
    custom_crop_name: str | None = None,
    custom_crop_water_tier: str = "medio",
    soil_override: dict[str, Any] | None = None,
    fertilizer_type: str = "quimico",
    tillage_mode: str = "convencional",
    main_concern: str = "sequia",
) -> dict[str, Any]:
    """
    Ejecuta el motor de simulación "What-If" de AgroShift a 3 años (6 ciclos)
    para la parcela y el cultivo base seleccionados, aceptando calibración manual de suelo
    y prácticas de fertilización / manejo de rastrojo.
    """
    climatology, cultivos, suelos = _load_datasets()

    if location_id not in climatology["locations"] or location_id not in suelos:
        valid_ids = sorted(suelos.keys())
        raise ValueError(f"location_id '{location_id}' no válido. Opciones: {valid_ids}")

    current_crop = str(current_crop or "Maiz_Grano").strip()
    valid_crop_ids = sorted(k for k in cultivos.keys() if k != "Barbecho_Suelo_Desnudo")
    if current_crop == "__otro__" or (custom_crop_name and current_crop not in valid_crop_ids):
        clean_name = str(custom_crop_name or "").strip() or "Cultivo Personalizado"
        tier = str(custom_crop_water_tier or "medio").strip().lower()
        if tier not in CUSTOM_CROP_PROFILES:
            tier = "medio"
        cultivos["__otro__"] = {
            "cultivo": "__otro__",
            "cultivo_label": clean_name,
            **CUSTOM_CROP_PROFILES[tier],
        }
        current_crop = "__otro__"
    elif current_crop not in valid_crop_ids:
        raise ValueError(f"current_crop '{current_crop}' no válido. Opciones: {valid_crop_ids}")

    hectares = max(0.1, float(hectares))
    rain_reduction_pct = min(max(0.0, float(rain_reduction_pct)), 0.80)
    temp_increase_c = min(max(0.0, float(temp_increase_c)), 3.0)
    irrigation_mode = str(irrigation_mode).strip().lower()
    if irrigation_mode not in {"temporal", "riego"}:
        irrigation_mode = "temporal"
    market_goal = str(market_goal).strip().lower()
    if market_goal not in {"grano", "forraje"}:
        market_goal = "grano"
    fertilizer_type = str(fertilizer_type or "quimico").strip().lower()
    if fertilizer_type not in FERTILIZER_LABELS:
        fertilizer_type = "quimico"
    tillage_mode = str(tillage_mode or "convencional").strip().lower()
    if tillage_mode not in TILLAGE_LABELS:
        tillage_mode = "convencional"
    main_concern = str(main_concern or "sequia").strip().lower()
    if main_concern not in CONCERN_LABELS:
        main_concern = "sequia"

    w_water, w_profit, w_nitrogen = _normalize_weights(weight_water, weight_profit, weight_nitrogen)

    loc_clim_months = climatology["locations"][location_id]["months"]
    soil, is_custom_soil, base_elevation_m = _apply_soil_override(suelos[location_id], soil_override)
    climate = _compute_parcel_climate_metrics(loc_clim_months, rain_reduction_pct, temp_increase_c)

    templates = _build_rotation_templates(location_id, current_crop, cultivos)
    evaluated_plans: list[dict[str, Any]] = []

    for tpl in templates:
        yearly_results: list[dict[str, Any]] = []
        prev_main_crop: str | None = None
        consec_mono = 0
        cum_n_cycles = 0
        is_baseline_plan = tpl["plan_id"] == "plan_actual"

        for y_spec in tpl["years"]:
            main_crop = y_spec["pv"] if y_spec["pv"] != "Barbecho_Suelo_Desnudo" else y_spec["oi"]
            if prev_main_crop is not None and main_crop == prev_main_crop:
                consec_mono += 1
            else:
                consec_mono = 0

            y_eval = _evaluate_year(
                year_spec=y_spec,
                prev_pv_crop=prev_main_crop,
                consecutive_monoculture_years=consec_mono,
                cumulative_n_fixed_cycles=cum_n_cycles,
                cultivos=cultivos,
                soil=soil,
                climate=climate,
                rain_reduction_pct=rain_reduction_pct,
                temp_increase_c=temp_increase_c,
                irrigation_mode=irrigation_mode,
                base_elevation_m=base_elevation_m,
                is_custom_soil=is_custom_soil,
                fertilizer_type=fertilizer_type,
                tillage_mode=tillage_mode,
                is_baseline_plan=is_baseline_plan,
            )
            yearly_results.append(y_eval)
            prev_main_crop = main_crop
            cum_n_cycles += y_eval["n_fixing_cycles"]

        total_eff_water_mm = sum(y["effective_water_demand_mm"] for y in yearly_results)
        total_cat_water_mm = sum(y["catalog_water_mm"] for y in yearly_results)
        total_net_income_ha = sum(y["adjusted_net_income_ha_mxn"] for y in yearly_results)
        total_net_income_mxn = total_net_income_ha * hectares
        total_n_savings_ha = sum(y["nitrogen_fertilizer_savings_ha_mxn"] for y in yearly_results)
        total_n_savings_mxn = total_n_savings_ha * hectares

        drought_overall = _aggregate_light([y["drought_light"] for y in yearly_results])
        frost_overall = _aggregate_light([y["frost_light"] for y in yearly_results])
        pest_overall = _aggregate_light([y["pest_light"] for y in yearly_results])

        months_protected = sum(y["months_soil_covered"] for y in yearly_results)
        months_bare = sum(y["months_bare_soil"] for y in yearly_results)
        total_n_cycles = sum(y["n_fixing_cycles"] for y in yearly_results)

        evaluated_plans.append(
            {
                "plan_id": tpl["plan_id"],
                "plan_name": tpl["plan_name"],
                "strategy_focus": tpl["strategy_focus"],
                "semaforo_sequia": drought_overall,
                "semaforo_heladas": frost_overall,
                "semaforo_plagas": pest_overall,
                "demanda_agua_efectiva_3a_mm": round(total_eff_water_mm, 1),
                "consumo_agua_catalogo_3a_mm": round(total_cat_water_mm, 1),
                "ingreso_neto_ha_3a_mxn": round(total_net_income_ha, 2),
                "ingreso_neto_total_mxn": round(total_net_income_mxn, 2),
                "ahorro_fertilizante_n_ha_3a_mxn": round(total_n_savings_ha, 2),
                "ahorro_fertilizante_n_total_mxn": round(total_n_savings_mxn, 2),
                "ahorro_agua_m3": 0.0,
                "consumo_agua_litros": 0,
                "ahorro_agua_litros": 0,
                "balance_nitrogeno_y_cobertura": {
                    "meses_suelo_protegido_3a": months_protected,
                    "meses_suelo_desnudo_3a": months_bare,
                    "ciclos_fijacion_nitrogeno_3a": total_n_cycles,
                    "meses_alerta_modis_parcela_3a": round(climate["bare_alert_expected_months_yr"] * 3.0, 1),
                    "meses_alerta_modis_mitigados_3a": (
                        round(climate["bare_alert_expected_months_yr"] * 3.0, 1) if months_bare == 0 else 0.0
                    ),
                },
                "years": yearly_results,
            }
        )

    baseline = evaluated_plans[0]
    baseline_water_mm = baseline["demanda_agua_efectiva_3a_mm"]
    baseline_water_m3 = round(baseline_water_mm * 10.0 * hectares, 1)
    current_crop_info = cultivos[current_crop]

    for plan in evaluated_plans:
        # 1 mm de lámina de agua en 1 ha equivale a 10 m³ (10,000 L)
        water_saved_mm = baseline_water_mm - plan["demanda_agua_efectiva_3a_mm"]
        plan_water_m3 = round(plan["demanda_agua_efectiva_3a_mm"] * 10.0 * hectares, 1)
        plan["consumo_agua_total_3a_m3"] = plan_water_m3
        plan["ahorro_agua_m3"] = round(water_saved_mm * 10.0 * hectares, 1)
        plan["consumo_agua_litros"] = int(round(plan_water_m3 * 1000.0))
        plan["ahorro_agua_litros"] = int(round((baseline_water_m3 - plan_water_m3) * 1000.0))

        # Sub-puntaje Agua (0-100): premia menor demanda efectiva, ahorro frente al plan actual y semáforo verde
        avg_drought_stress = sum(y["drought_stress_index"] for y in plan["years"]) / 3.0
        light_water_bonus = {"VERDE": 14.0, "AMARILLO": 0.0, "ROJO": -18.0}[plan["semaforo_sequia"]]
        water_savings_bonus = min(28.0, max(-10.0, (water_saved_mm / 650.0) * 28.0))
        water_score = max(
            5.0,
            min(100.0, 100.0 - max(0.0, avg_drought_stress - 55.0) * 1.05 + water_savings_bonus + light_water_bonus),
        )

        # Sub-puntaje Rentabilidad Ajustada por Riesgo (0-100)
        profit_raw = (plan["ingreso_neto_ha_3a_mxn"] / 92000.0) * 100.0
        pest_frost_penalty = (
            (8.0 if plan["semaforo_plagas"] == "ROJO" else 3.0 if plan["semaforo_plagas"] == "AMARILLO" else 0.0)
            + (8.0 if plan["semaforo_heladas"] == "ROJO" else 3.0 if plan["semaforo_heladas"] == "AMARILLO" else 0.0)
        )
        profit_score = max(5.0, min(100.0, profit_raw - pest_frost_penalty))

        # Sub-puntaje Nitrógeno, Materia Orgánica y Control de Erosión (0-100)
        n_cycles = plan["balance_nitrogeno_y_cobertura"]["ciclos_fijacion_nitrogeno_3a"]
        months_bare = plan["balance_nitrogeno_y_cobertura"]["meses_suelo_desnudo_3a"]
        cover_ratio = plan["balance_nitrogeno_y_cobertura"]["meses_suelo_protegido_3a"] / 36.0
        n_bonus = min(52.0, n_cycles * 24.0)
        cover_bonus = cover_ratio * 42.0
        soil_need_bonus = 6.0 if (n_cycles >= 2 and int(soil["needs_nitrogen_fixation"]) == 1) else 0.0

        soil_urgency_adj = 0.0
        if is_custom_soil:
            mo_val = float(soil["materia_organica_pct"])
            slope_val = float(soil["pendiente_pct"])
            e_risk_val = int(soil["erosion_risk_score"])
            if mo_val < 1.5:
                mo_deficit = 1.5 - mo_val
                if n_cycles >= 2:
                    soil_need_bonus += mo_deficit * 14.0
                    soil_urgency_adj += mo_deficit * 8.5
                elif n_cycles == 1:
                    soil_need_bonus += mo_deficit * 5.0
                else:
                    soil_need_bonus -= mo_deficit * 12.0
                    soil_urgency_adj -= mo_deficit * 6.0

            if slope_val >= 5.0 or e_risk_val >= 3:
                slope_excess = max(0.0, slope_val - 4.0)
                erosion_factor = 3.0 + slope_excess * 1.1 + (2.5 if e_risk_val >= 3 else 0.0)
                if months_bare == 0:
                    soil_need_bonus += erosion_factor
                    soil_urgency_adj += erosion_factor * (1.15 if plan["plan_id"] == "plan_regenerativo" else 0.75)
                else:
                    soil_need_bonus -= erosion_factor * 1.5
                    soil_urgency_adj -= erosion_factor * 1.2

        if tillage_mode == "convencional" and int(soil["erosion_risk_score"]) >= 3:
            if months_bare == 0:
                soil_need_bonus += 3.5
            else:
                soil_need_bonus -= 5.0

        nitrogen_score = max(5.0, min(100.0, n_bonus + cover_bonus + soil_need_bonus))

        # Ajuste por objetivo comercial del productor (grano vs forraje)
        active_crops = [y["pv_crop_id"] for y in plan["years"] if y["pv_crop_id"] != "Barbecho_Suelo_Desnudo"] + [
            y["oi_crop_id"] for y in plan["years"] if y["oi_crop_id"] != "Barbecho_Suelo_Desnudo"
        ]
        if market_goal == "forraje":
            forage_ratio = sum(1 for c in active_crops if c in FORAGE_CROPS) / max(1, len(active_crops))
            market_alignment_bonus = (forage_ratio - 0.35) * 12.0
        else:
            grain_count = sum(1 for c in active_crops if c in GRAIN_CROPS)
            market_alignment_bonus = 2.0 if grain_count >= 2 else 0.0

        # Impulso de idoneidad según la preocupación principal del agricultor (main_concern)
        concern_alignment_bonus = 0.0
        if main_concern == "sequia":
            if plan["plan_id"] == "plan_conservacion_hidrica":
                concern_alignment_bonus = 4.2
            elif plan["plan_id"] == "plan_regenerativo":
                concern_alignment_bonus = 1.8
            else:
                concern_alignment_bonus = -3.0
        elif main_concern == "suelo":
            if plan["plan_id"] == "plan_regenerativo":
                concern_alignment_bonus = 4.8
            elif plan["plan_id"] == "plan_conservacion_hidrica":
                concern_alignment_bonus = 2.0
            else:
                concern_alignment_bonus = -3.5
        elif main_concern == "plagas":
            if plan["semaforo_plagas"] == "VERDE":
                concern_alignment_bonus = 3.8 if plan["plan_id"] == "plan_regenerativo" else 3.2
            elif plan["semaforo_plagas"] == "ROJO":
                concern_alignment_bonus = -4.0
        elif main_concern == "heladas":
            if plan["semaforo_heladas"] == "VERDE" and months_bare == 0:
                concern_alignment_bonus = 3.8
            elif months_bare == 0:
                concern_alignment_bonus = 2.0
            else:
                concern_alignment_bonus = -3.0

        suitability = max(
            5.0,
            min(
                100.0,
                w_water * water_score
                + w_profit * profit_score
                + w_nitrogen * nitrogen_score
                + market_alignment_bonus
                + soil_urgency_adj
                + concern_alignment_bonus,
            ),
        )
        plan["component_scores"] = {
            "water_score": round(water_score, 1),
            "profit_score": round(profit_score, 1),
            "nitrogen_soil_score": round(nitrogen_score, 1),
        }
        plan["suitability_score"] = round(suitability, 2)
        plan["nasa_evidence_summary"] = _build_nasa_evidence_summary(
            plan_id=plan["plan_id"],
            plan_name=plan["plan_name"],
            current_crop_info=current_crop_info,
            soil=soil,
            climate=climate,
            rain_reduction_pct=rain_reduction_pct,
            temp_increase_c=temp_increase_c,
            hectares=hectares,
            plan_metrics=plan,
            baseline_metrics=baseline,
            is_custom_soil=is_custom_soil,
            fertilizer_type=fertilizer_type,
        )
        plan["local_validation_notes"] = _build_local_validation_notes(
            plan_metrics=plan,
            soil=soil,
            irrigation_mode=irrigation_mode,
            market_goal=market_goal,
            current_crop_label=current_crop_info["cultivo_label"],
        )

    ranked = sorted(evaluated_plans, key=lambda p: p["suitability_score"], reverse=True)
    recommended = ranked[0]

    return {
        "location_id": location_id,
        "zona_label": soil["zona_label"],
        "municipio": soil["municipio"],
        "hectares": hectares,
        "current_crop": current_crop,
        "current_crop_label": current_crop_info["cultivo_label"],
        "current_crop_cycle_label": current_crop_info["ciclo_label"],
        "rain_reduction_pct": rain_reduction_pct,
        "temp_increase_c": temp_increase_c,
        "irrigation_mode": irrigation_mode,
        "market_goal": market_goal,
        "fertilizer_type": fertilizer_type,
        "fertilizer_label": FERTILIZER_LABELS[fertilizer_type],
        "tillage_mode": tillage_mode,
        "tillage_label": TILLAGE_LABELS[tillage_mode],
        "main_concern": main_concern,
        "main_concern_label": CONCERN_LABELS[main_concern],
        "is_custom_soil": is_custom_soil,
        "normalized_weights": {
            "weight_water": round(w_water, 4),
            "weight_profit": round(w_profit, 4),
            "weight_nitrogen": round(w_nitrogen, 4),
        },
        "parcel_context": {
            "is_custom_soil": is_custom_soil,
            "tipo_suelo_label": soil["tipo_suelo_label"],
            "textura_label": soil["textura_label"],
            "retencion_agua": soil["retencion_agua"],
            "riesgo_erosion": soil["riesgo_erosion"],
            "local_elevation_m": soil["local_elevation_m"],
            "pendiente_pct": soil["pendiente_pct"],
            "materia_organica_pct": soil["materia_organica_pct"],
            "water_retention_score": soil["water_retention_score"],
            "erosion_risk_score": soil["erosion_risk_score"],
            "problema_principal": soil["problema_principal"],
            "fertilizer_type": fertilizer_type,
            "fertilizer_label": FERTILIZER_LABELS[fertilizer_type],
            "tillage_mode": tillage_mode,
            "tillage_label": TILLAGE_LABELS[tillage_mode],
            "main_concern": main_concern,
            "main_concern_label": CONCERN_LABELS[main_concern],
            "annual_historical_rain_mm": round(climate["rain_hist_annual_mm"], 1),
            "annual_simulated_rain_mm": round(climate["rain_adj_annual_mm"], 1),
            "annual_frost_days": round(climate["frost_days_annual"], 1),
            "annual_pest_risk_days": round(climate["pest_days_annual"], 1),
            "expected_bare_soil_alert_months_yr": round(climate["bare_alert_expected_months_yr"], 2),
        },
        "recommended_plan_id": recommended["plan_id"],
        "recommended_plan_name": recommended["plan_name"],
        "recommended_suitability_score": recommended["suitability_score"],
        "plans": evaluated_plans,
    }

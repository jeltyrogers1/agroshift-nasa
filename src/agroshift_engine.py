from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
CLIMATOLOGY_PATH = BASE_DIR / "data" / "processed" / "agroshift_climatology_12m.json"
CULTIVOS_CSV_PATH = BASE_DIR / "data" / "processed" / "cultivos_coahuila_168_variedades_oficial.csv"
CULTIVOS_PATH = CULTIVOS_CSV_PATH  # Alias retrocompatible
SUELOS_PATH = BASE_DIR / "data" / "processed" / "suelos_coahuila_clean.json"

PV_MONTHS = {3, 4, 5, 6, 7, 8}
OI_MONTHS = {9, 10, 11, 12, 1, 2}

SIAP_CATEGORY_ORDER = [
    "Granos_y_Leguminosas",
    "Forrajes",
    "Hortalizas",
    "Industriales_y_Oleaginosas",
    "Frutales_Perennes",
]

SIAP_CATEGORY_LABELS = {
    "Granos_y_Leguminosas": "Granos y Leguminosas",
    "Forrajes": "Forrajes",
    "Hortalizas": "Hortalizas",
    "Industriales_y_Oleaginosas": "Industriales y Oleaginosas",
    "Frutales_Perennes": "Frutales Perennes",
}

FAMILY_LABELS = {
    "Maiz": "Maíz",
    "Frijol": "Frijol",
    "Avena_Grano": "Avena Grano",
    "Cebada_Grano": "Cebada Grano",
    "Sorgo_Grano": "Sorgo Grano",
    "Trigo_Grano": "Trigo Grano",
    "Alfalfa": "Alfalfa",
    "Avena_Forrajera": "Avena Forrajera",
    "Cebada_Forrajera": "Cebada Forrajera",
    "Maiz_Forrajero": "Maíz Forrajero",
    "Pastos_y_Praderas": "Pastos y Praderas",
    "Sorgo_Forrajero": "Sorgo Forrajero",
    "Calabacita": "Calabacita",
    "Cebolla": "Cebolla",
    "Chile_Verde": "Chile Verde",
    "Melon": "Melón",
    "Nopal_Verdura": "Nopal Verdura",
    "Papa": "Papa",
    "Repollo_Col_y_Brassicaceas": "Repollo / Col y Brassicáceas",
    "Sandia": "Sandía",
    "Tomate_Rojo": "Tomate Rojo",
    "Tomate_Verde": "Tomate Verde",
    "Zanahoria_y_Lechuga": "Zanahoria y Lechuga",
    "Algodon_Hueso": "Algodón Hueso",
    "Cartamo_y_Girasol": "Cártamo y Girasol",
    "Durazno_Chabacano_y_Membrillo": "Durazno, Chabacano y Membrillo",
    "Higo_y_Granada": "Higo y Granada",
    "Manzana": "Manzana",
    "Nogal_Pecanero": "Nogal Pecanero",
    "Nopal_Tunero_y_Maguey": "Nopal Tunero y Maguey",
    "Uva_Vid": "Uva / Vid",
}

ORDINAL_SCORES = {
    "Nula": 0,
    "Baja": 1,
    "Media": 2,
    "Alta": 3,
    "Muy_Alta": 4,
}

# Economía de referencia por familia SIAP (MXN/ha/ciclo o año productivo en perennes)
# Mantiene exactamente los valores base históricos de granos y forrajes en Coahuila.
FAMILY_ECONOMICS: dict[str, dict[str, float]] = {
    "Maiz": {"rendimiento_ton_ha": 4.5, "precio_ton_mxn": 6200.0, "costo_ha_mxn": 16500.0},
    "Frijol": {"rendimiento_ton_ha": 1.4, "precio_ton_mxn": 21000.0, "costo_ha_mxn": 14000.0},
    "Avena_Forrajera": {"rendimiento_ton_ha": 18.0, "precio_ton_mxn": 1450.0, "costo_ha_mxn": 11500.0},
    "Sorgo_Forrajero": {"rendimiento_ton_ha": 22.0, "precio_ton_mxn": 1250.0, "costo_ha_mxn": 12000.0},
    "Alfalfa": {"rendimiento_ton_ha": 28.0, "precio_ton_mxn": 1850.0, "costo_ha_mxn": 24000.0},
    "Cebada_Forrajera": {"rendimiento_ton_ha": 16.5, "precio_ton_mxn": 1400.0, "costo_ha_mxn": 10800.0},
    "Avena_Grano": {"rendimiento_ton_ha": 3.0, "precio_ton_mxn": 6800.0, "costo_ha_mxn": 10200.0},
    "Cebada_Grano": {"rendimiento_ton_ha": 3.5, "precio_ton_mxn": 6600.0, "costo_ha_mxn": 11500.0},
    "Sorgo_Grano": {"rendimiento_ton_ha": 4.5, "precio_ton_mxn": 5400.0, "costo_ha_mxn": 12300.0},
    "Trigo_Grano": {"rendimiento_ton_ha": 4.8, "precio_ton_mxn": 6500.0, "costo_ha_mxn": 17200.0},
    "Maiz_Forrajero": {"rendimiento_ton_ha": 42.0, "precio_ton_mxn": 950.0, "costo_ha_mxn": 21500.0},
    "Pastos_y_Praderas": {"rendimiento_ton_ha": 24.0, "precio_ton_mxn": 1250.0, "costo_ha_mxn": 13500.0},
    "Algodon_Hueso": {"rendimiento_ton_ha": 4.2, "precio_ton_mxn": 16500.0, "costo_ha_mxn": 44500.0},
    "Cartamo_y_Girasol": {"rendimiento_ton_ha": 2.1, "precio_ton_mxn": 11500.0, "costo_ha_mxn": 11200.0},
    "Calabacita": {"rendimiento_ton_ha": 20.0, "precio_ton_mxn": 7200.0, "costo_ha_mxn": 98000.0},
    "Cebolla": {"rendimiento_ton_ha": 35.0, "precio_ton_mxn": 6200.0, "costo_ha_mxn": 162000.0},
    "Chile_Verde": {"rendimiento_ton_ha": 22.0, "precio_ton_mxn": 10500.0, "costo_ha_mxn": 168000.0},
    "Melon": {"rendimiento_ton_ha": 34.0, "precio_ton_mxn": 6800.0, "costo_ha_mxn": 165000.0},
    "Nopal_Verdura": {"rendimiento_ton_ha": 36.0, "precio_ton_mxn": 4600.0, "costo_ha_mxn": 115000.0},
    "Papa": {"rendimiento_ton_ha": 30.0, "precio_ton_mxn": 8200.0, "costo_ha_mxn": 158000.0},
    "Repollo_Col_y_Brassicaceas": {"rendimiento_ton_ha": 32.0, "precio_ton_mxn": 5800.0, "costo_ha_mxn": 132000.0},
    "Sandia": {"rendimiento_ton_ha": 38.0, "precio_ton_mxn": 5200.0, "costo_ha_mxn": 142000.0},
    "Tomate_Rojo": {"rendimiento_ton_ha": 45.0, "precio_ton_mxn": 7500.0, "costo_ha_mxn": 255000.0},
    "Tomate_Verde": {"rendimiento_ton_ha": 22.0, "precio_ton_mxn": 7500.0, "costo_ha_mxn": 118000.0},
    "Zanahoria_y_Lechuga": {"rendimiento_ton_ha": 28.0, "precio_ton_mxn": 6200.0, "costo_ha_mxn": 122000.0},
    "Durazno_Chabacano_y_Membrillo": {"rendimiento_ton_ha": 14.0, "precio_ton_mxn": 14000.0, "costo_ha_mxn": 126000.0},
    "Higo_y_Granada": {"rendimiento_ton_ha": 12.0, "precio_ton_mxn": 16500.0, "costo_ha_mxn": 125000.0},
    "Manzana": {"rendimiento_ton_ha": 22.0, "precio_ton_mxn": 13500.0, "costo_ha_mxn": 195000.0},
    "Nogal_Pecanero": {"rendimiento_ton_ha": 1.85, "precio_ton_mxn": 82000.0, "costo_ha_mxn": 74000.0},
    "Nopal_Tunero_y_Maguey": {"rendimiento_ton_ha": 16.0, "precio_ton_mxn": 5500.0, "costo_ha_mxn": 52000.0},
    "Uva_Vid": {"rendimiento_ton_ha": 11.0, "precio_ton_mxn": 18000.0, "costo_ha_mxn": 118000.0},
}

LEGACY_CROP_ALIASES = {
    "Maiz_Grano",
    "Frijol_Pinto",
    "Avena_Forrajera",
    "Cebada_Forrajera",
    "Sorgo_Forrajero",
    "Alfalfa",
}

LIGHT_PHRASE_MAP = {
    "VERDE": "estado VERDE",
    "AMARILLO": "alerta AMARILLA",
    "ROJO": "alerta ROJA",
}

FALLOW_CROP: dict[str, Any] = {
    "cultivo": "Barbecho_Suelo_Desnudo",
    "familia_cultivo": "Barbecho",
    "nombre_comun": "Barbecho (Suelo Desnudo)",
    "clasificacion_oficial": "Sin_Cultivo",
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
    "ciclo_norm": "Otono-Invierno",
    "ciclo_label": "Otoño-Invierno",
    "dias_madurez": "0",
    "modalidad_hidrica_tipica": "Sin cultivo",
    "municipios_coahuila": "Coahuila",
    "fuente_oficial": "Referencia base Kultiva",
    "beneficio_principal": "Suelo expuesto sin cobertura vegetal",
    "categoria_siap": "Sin_Cobertura",
    "modo_en_kultiva": "Sin_Cobertura",
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
        "ciclo_norm": "Primavera-Verano",
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
        "ciclo_norm": "Primavera-Verano",
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
        "ciclo_norm": "Primavera-Verano",
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


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", str(text or "")) if unicodedata.category(ch) != "Mn"
    ).lower()


def _derive_cultivo_label(nombre_comun: str) -> str:
    """Construye una etiqueta legible y compacta preservando el nombre común oficial sin abreviar datos."""
    def _repl(match: re.Match[str]) -> str:
        inner = match.group(0).strip()
        if inner.startswith("(var."):
            return " " + inner
        if "ej." in inner or len(inner) > 28:
            return ""
        return " " + inner

    cleaned = re.sub(r"\s*\([^)]*\)", _repl, nombre_comun).strip()
    return re.sub(r"\s{2,}", " ", cleaned) or nombre_comun


def _normalize_ciclo(ciclo_raw: str, modo_en_kultiva: str) -> tuple[str, str]:
    ciclo = str(ciclo_raw or "Primavera-Verano").strip()
    if modo_en_kultiva == "Cobertura_Intercalada_Perenne":
        ciclo_norm = "Perenne" if ciclo == "Perenne" else "Todo_el_ano"
    elif ciclo == "Todo_el_ano" or ciclo.startswith("Perenne"):
        ciclo_norm = "Todo_el_ano"
    elif ciclo.startswith("Otono-Invierno"):
        ciclo_norm = "Otono-Invierno"
    else:
        ciclo_norm = "Primavera-Verano"

    ciclo_label = (
        ciclo.replace("Otono-Invierno", "Otoño-Invierno")
        .replace("Todo_el_ano", "Todo el año")
        .replace("otono", "otoño")
    )
    return ciclo_norm, ciclo_label


def _enrich_csv_crop_row(row: dict[str, str]) -> dict[str, Any]:
    cultivo_id = row["cultivo"].strip()
    familia = row["familia_cultivo"].strip()
    nombre_comun = row["nombre_comun"].strip()
    modo = row["modo_en_kultiva"].strip()
    ciclo_norm, ciclo_label = _normalize_ciclo(row["ciclo_siembra"].strip(), modo)

    fija_n_bin = 1 if row["fija_nitrogeno"].strip() == "Si" else 0
    erosion_score = ORDINAL_SCORES.get(row["reduce_erosion"].strip(), 2)
    drought_score = ORDINAL_SCORES.get(row["tolerancia_sequia"].strip(), 2)
    frost_score = ORDINAL_SCORES.get(row["tolerancia_heladas"].strip(), 2)

    econ = FAMILY_ECONOMICS.get(
        familia,
        {"rendimiento_ton_ha": 4.0, "precio_ton_mxn": 6000.0, "costo_ha_mxn": 13000.0},
    )
    rend = float(econ["rendimiento_ton_ha"])
    precio = float(econ["precio_ton_mxn"])
    costo = float(econ["costo_ha_mxn"])
    ingreso_bruto = round(rend * precio, 2)
    ingreso_neto = round(ingreso_bruto - costo, 2)

    return {
        "cultivo": cultivo_id,
        "familia_cultivo": familia,
        "nombre_comun": nombre_comun,
        "clasificacion_oficial": row["clasificacion_oficial"].strip(),
        "tipo_rotacion": row["tipo_rotacion"].strip(),
        "consumo_agua_mm": float(row["consumo_agua_mm"]),
        "temp_min_c": float(row["temp_min_c"]),
        "temp_max_c": float(row["temp_max_c"]),
        "umbral_helada_c": float(row["umbral_helada_c"]),
        "profundidad_raiz_cm": int(float(row["profundidad_raiz_cm"])),
        "fija_nitrogeno": row["fija_nitrogeno"].strip(),
        "reduce_erosion": row["reduce_erosion"].strip(),
        "tolerancia_sequia": row["tolerancia_sequia"].strip(),
        "tolerancia_heladas": row["tolerancia_heladas"].strip(),
        "ciclo_siembra": row["ciclo_siembra"].strip(),
        "dias_madurez": row["dias_madurez"].strip(),
        "modalidad_hidrica_tipica": row["modalidad_hidrica_tipica"].strip(),
        "municipios_coahuila": row["municipios_coahuila"].strip(),
        "fuente_oficial": row["fuente_oficial"].strip(),
        "beneficio_principal": row["beneficio_principal"].strip(),
        "categoria_siap": row["categoria_siap"].strip(),
        "modo_en_kultiva": modo,
        # Campos derivados para el motor y la interfaz
        "cultivo_label": _derive_cultivo_label(nombre_comun),
        "ciclo_norm": ciclo_norm,
        "ciclo_label": ciclo_label,
        "fija_nitrogeno_bin": fija_n_bin,
        "erosion_control_score": erosion_score,
        "drought_tolerance_score": drought_score,
        "frost_tolerance_score": frost_score,
        "rendimiento_ton_ha": rend,
        "precio_ton_mxn": precio,
        "costo_ha_mxn": costo,
        "ingreso_bruto_ha_mxn": ingreso_bruto,
        "ingreso_neto_ha_mxn": ingreso_neto,
        "profit_score": 3 if ingreso_neto >= 50000 else (2 if ingreso_neto >= 13000 else 1),
    }


def _load_official_cultivos_list() -> list[dict[str, Any]]:
    with CULTIVOS_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [_enrich_csv_crop_row(row) for row in reader if row.get("cultivo")]


def get_official_catalog_payload() -> dict[str, Any]:
    """Devuelve las 168 variedades oficiales, las 31 familias y la agrupación por categoría SIAP para /api/init."""
    variedades = _load_official_cultivos_list()
    by_family: dict[str, list[dict[str, Any]]] = {}
    for item in variedades:
        by_family.setdefault(item["familia_cultivo"], []).append(item)

    familias_list: list[dict[str, Any]] = []
    by_category: dict[str, list[dict[str, Any]]] = {cat: [] for cat in SIAP_CATEGORY_ORDER}

    for fam_id in sorted(by_family.keys(), key=lambda k: FAMILY_LABELS.get(k, k)):
        items = by_family[fam_id]
        cat_id = items[0]["categoria_siap"]
        fam_entry = {
            "familia_cultivo": fam_id,
            "familia_label": FAMILY_LABELS.get(fam_id, fam_id.replace("_", " ")),
            "categoria_siap": cat_id,
            "categoria_label": SIAP_CATEGORY_LABELS.get(cat_id, cat_id.replace("_", " ")),
            "modo_en_kultiva": items[0]["modo_en_kultiva"],
            "variedades_count": len(items),
            "consumo_agua_min_mm": min(int(v["consumo_agua_mm"]) for v in items),
            "consumo_agua_max_mm": max(int(v["consumo_agua_mm"]) for v in items),
            "variedades_ids": [v["cultivo"] for v in items],
        }
        familias_list.append(fam_entry)
        by_category.setdefault(cat_id, []).append(
            {
                **fam_entry,
                "variedades": items,
            }
        )

    catalogo_agrupado = [
        {
            "categoria_siap": cat_id,
            "categoria_label": SIAP_CATEGORY_LABELS.get(cat_id, cat_id.replace("_", " ")),
            "familias": by_category.get(cat_id, []),
        }
        for cat_id in SIAP_CATEGORY_ORDER
        if by_category.get(cat_id)
    ]

    return {
        "cultivos": variedades,
        "familias_cultivo": familias_list,
        "catalogo_agrupado": catalogo_agrupado,
        "total_variedades": len(variedades),
        "total_familias": len(familias_list),
    }


def _load_datasets() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    with CLIMATOLOGY_PATH.open("r", encoding="utf-8") as f:
        climatology = json.load(f)
    cultivos_list = _load_official_cultivos_list()
    with SUELOS_PATH.open("r", encoding="utf-8") as f:
        suelos_list = json.load(f)

    cultivos = {c["cultivo"]: c for c in cultivos_list}
    cultivos["Barbecho_Suelo_Desnudo"] = dict(FALLOW_CROP)
    suelos = {s["location_id"]: s for s in suelos_list}
    return climatology, cultivos, suelos


def _is_forage_crop(crop_info: dict[str, Any]) -> bool:
    return (
        crop_info.get("categoria_siap") == "Forrajes"
        or crop_info.get("familia_cultivo") in {
            "Alfalfa",
            "Avena_Forrajera",
            "Cebada_Forrajera",
            "Maiz_Forrajero",
            "Pastos_y_Praderas",
            "Sorgo_Forrajero",
        }
        or "Forrajero" in str(crop_info.get("cultivo", ""))
    )


def _is_grain_or_commercial_crop(crop_info: dict[str, Any]) -> bool:
    if crop_info.get("cultivo") == "Barbecho_Suelo_Desnudo":
        return False
    return not _is_forage_crop(crop_info)


def _site_location_tokens(location_id: str, soil: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Devuelve tokens de localidad/municipio prioritarios y tokens incompatibles según parcela y altitud."""
    muni_norm = _strip_accents(soil.get("municipio", "").replace("_", " "))
    elev_m = float(soil.get("local_elevation_m", 1700.0))

    preferred: list[str] = []
    if muni_norm:
        preferred.append(muni_norm)

    if location_id == "Los_Lirios_Arteaga" or elev_m >= 2000.0:
        preferred.extend(["arteaga", "los lirios", "sierra", "valles altos", "altura", "jame", "alazanas"])
        incompatible = ["comarca lagunera", "no apto sierra", "zona calida"]
    elif location_id == "General_Cepeda" or (elev_m < 1600.0 and int(soil.get("water_retention_score", 2)) == 1):
        preferred.extend(["general cepeda", "semiarido", "arido", "valles calidos", "calido"])
        incompatible = ["sierra alta", ">2,000 msnm", ">2,100 msnm", "temporal de sierra"]
    else:  # UAAAN_La_Narro / valles templados 1,600-1,999 msnm
        preferred.extend(["saltillo", "la narro", "sureste de coahuila", "valles templados"])
        incompatible = ["no apto"]

    return preferred, incompatible


def _score_variety_for_site(
    crop: dict[str, Any],
    location_id: str,
    soil: dict[str, Any],
    irrigation_mode: str,
    market_goal: str,
    concerns: list[str],
) -> float:
    """Evalúa idoneidad agronómica de una variedad oficial respecto a municipio, altitud, heladas e irrigación."""
    elev_m = float(soil.get("local_elevation_m", 1700.0))
    is_high_alt = elev_m >= 2000.0 or location_id == "Los_Lirios_Arteaga"
    is_arid = location_id == "General_Cepeda" or (int(soil.get("water_retention_score", 2)) == 1 and elev_m < 1700.0)

    munis_text = _strip_accents(crop.get("municipios_coahuila", ""))
    benefit_text = _strip_accents(crop.get("beneficio_principal", ""))
    modal_text = _strip_accents(crop.get("modalidad_hidrica_tipica", ""))
    combined_geo = f"{munis_text} {benefit_text}"

    preferred_tokens, incompatible_tokens = _site_location_tokens(location_id, soil)
    score = 0.0

    # 1. Adaptación geográfica / municipio en Coahuila
    for idx, tok in enumerate(preferred_tokens):
        if tok in munis_text:
            score += 24.0 if idx < 2 else 10.0
        elif tok in benefit_text:
            score += 8.0

    for tok in incompatible_tokens:
        if tok in combined_geo and not any(p in munis_text for p in preferred_tokens[:2]):
            score -= 22.0

    # 2. Altitud y riesgo de heladas
    frost_score = int(crop.get("frost_tolerance_score", 2))
    umbral_helada = float(crop.get("umbral_helada_c", 1.0))
    temp_min = float(crop.get("temp_min_c", 8.0))

    if is_high_alt:
        score += frost_score * 10.0
        score -= max(0.0, umbral_helada) * 4.0
        score -= max(0.0, temp_min - 7.0) * 1.4
        if "sierra" in combined_geo or "los lirios" in combined_geo or "arteaga" in munis_text:
            score += 14.0
        if "no apto sierra" in combined_geo:
            score -= 60.0
        if "partes bajas" in munis_text and "los lirios" not in munis_text:
            score -= 10.0
    elif is_arid:
        temp_max = float(crop.get("temp_max_c", 35.0))
        drought_score = int(crop.get("drought_tolerance_score", 2))
        score += drought_score * 8.0
        score += max(0.0, temp_max - 33.0) * 2.5
        if "salin" in combined_geo or "calcare" in combined_geo:
            score += 5.0
    else:  # Valles templados (UAAAN La Narro / Saltillo)
        score += frost_score * 4.0 + int(crop.get("drought_tolerance_score", 2)) * 4.0
        if "la narro" in munis_text:
            score += 18.0
        elif "saltillo" in munis_text:
            score += 10.0

    if "heladas" in concerns:
        score += frost_score * 6.0 - umbral_helada * 2.0

    # 3. Modalidad hídrica (temporal vs riego/auxilio)
    has_temporal = "temporal" in modal_text or "residual" in modal_text or "agostadero" in modal_text
    has_auxilio = "auxilio" in modal_text or "deficitario" in modal_text or "acequia" in modal_text
    has_riego = "riego" in modal_text or "goteo" in modal_text or "fertirrigacion" in modal_text
    is_protected_only = "invernadero" in modal_text and "campo" not in benefit_text and "cielo abierto" not in benefit_text

    water_mm = float(crop.get("consumo_agua_mm", 400.0))
    drought_score = int(crop.get("drought_tolerance_score", 2))

    if irrigation_mode == "temporal":
        if has_temporal:
            score += 26.0
        elif has_auxilio:
            score += 8.0
        elif has_riego:
            score -= 20.0
        if is_protected_only:
            score -= 18.0
        score += drought_score * 7.0
        score -= (water_mm - 300.0) * 0.04
    else:  # riego / auxilio
        if has_riego or has_auxilio:
            score += 18.0
        if "estandar comercial" in _strip_accents(crop.get("nombre_comun", "")) or "dominante" in benefit_text:
            score += 10.0
        if "agricultura por contrato" in modal_text or "tecnificado" in modal_text:
            score += 6.0

    if "sequia" in concerns or int(soil.get("high_drought_vulnerability", 0)) == 1:
        score += drought_score * 5.0 - (water_mm - 300.0) * 0.03

    # 4. Suelo y erosión
    if int(soil.get("needs_erosion_cover", 0)) == 1 or int(soil.get("erosion_risk_score", 2)) >= 3:
        score += int(crop.get("erosion_control_score", 2)) * 5.0

    # 5. Objetivo comercial (grano/comercial vs forraje)
    if market_goal == "forraje":
        if _is_forage_crop(crop) or "forraj" in _strip_accents(crop["nombre_comun"]):
            score += 14.0
    else:
        if not ("forraj" in _strip_accents(crop["nombre_comun"]) and crop["familia_cultivo"] in {"Maiz", "Cartamo_y_Girasol"}):
            score += 6.0

    return score


def _resolve_crop_selection(
    requested_crop: str,
    cultivos: dict[str, dict[str, Any]],
    location_id: str,
    soil: dict[str, Any],
    irrigation_mode: str,
    market_goal: str,
    concerns: list[str],
    custom_crop_name: str | None = None,
    custom_crop_water_tier: str = "medio",
) -> tuple[str, str]:
    """
    Resuelve `requested_crop` contra las 168 variedades oficiales:
    - Variedad específica -> se usa directamente.
    - Familia general (31 familias) -> elige automáticamente la mejor variedad para el sitio.
    - IDs legacy anteriores (`Maiz_Grano`, `Frijol_Pinto`, etc.) -> resueltos con retrocompatibilidad total.
    - `"__otro__"` -> perfil personalizado de respaldo.
    Devuelve `(resolved_crop_id, selection_mode)`.
    """
    req = str(requested_crop or "Maiz_Grano").strip()
    valid_varieties = {k: v for k, v in cultivos.items() if k != "Barbecho_Suelo_Desnudo"}

    if req in valid_varieties:
        return req, "variedad_oficial"

    # Familias oficiales (31) y aliases retrocompatibles
    candidates: list[dict[str, Any]] = []
    sel_mode = "familia_auto"

    if req == "Maiz_Grano":
        sel_mode = "legacy_alias"
        candidates = [
            v
            for v in valid_varieties.values()
            if v["familia_cultivo"] == "Maiz" and "forrajero" not in v["cultivo"].lower() and "elotero" not in v["cultivo"].lower()
        ]
    elif req == "Frijol_Pinto":
        sel_mode = "legacy_alias"
        candidates = [
            v
            for v in valid_varieties.values()
            if v["familia_cultivo"] == "Frijol" and "pinto" in v["cultivo"].lower()
        ]
    else:
        fam_matches = [v for v in valid_varieties.values() if v["familia_cultivo"] == req]
        if fam_matches:
            candidates = fam_matches
            sel_mode = "legacy_alias" if req in LEGACY_CROP_ALIASES else "familia_auto"

    if candidates:
        best = max(
            candidates,
            key=lambda c: (
                _score_variety_for_site(c, location_id, soil, irrigation_mode, market_goal, concerns),
                -float(c["consumo_agua_mm"]),
                c["cultivo"],
            ),
        )
        return best["cultivo"], sel_mode

    if req == "__otro__" or (custom_crop_name and req not in valid_varieties):
        clean_name = str(custom_crop_name or "").strip() or "Cultivo Personalizado"
        tier = str(custom_crop_water_tier or "medio").strip().lower()
        if tier not in CUSTOM_CROP_PROFILES:
            tier = "medio"
        cultivos["__otro__"] = {
            "cultivo": "__otro__",
            "familia_cultivo": "Personalizado",
            "nombre_comun": clean_name,
            "clasificacion_oficial": "Cultivo_Personalizado_Usuario",
            "cultivo_label": clean_name,
            "dias_madurez": "Variable",
            "modalidad_hidrica_tipica": "Definida por productor",
            "municipios_coahuila": soil.get("municipio", "Coahuila"),
            "fuente_oficial": "Perfil agronómico de respaldo Kultiva (estimación por nivel hídrico)",
            "beneficio_principal": "Simulación personalizada según consumo de agua seleccionado",
            "categoria_siap": "Personalizado",
            "modo_en_kultiva": "Rotacion_Ciclica",
            **CUSTOM_CROP_PROFILES[tier],
        }
        return "__otro__", "personalizado"

    valid_options = sorted(list(valid_varieties.keys()) + sorted({v["familia_cultivo"] for v in valid_varieties.values()}))
    raise ValueError(f"current_crop '{req}' no válido. Opciones de ejemplo: {valid_options[:12]}...")


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

    elev_raw = soil_override.get(
        "local_elevation_m",
        soil_override.get("elevacion_msnm", soil_override.get("elevacion_m")),
    )
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


def _select_rotation_partners(
    location_id: str,
    soil: dict[str, Any],
    market_goal: str,
    current_crop: str,
    crop_info: dict[str, Any],
) -> dict[str, str]:
    """Elige variedades oficiales específicas para rotación respetando altitud/frío, aridez y familia base."""
    elev_m = float(soil.get("local_elevation_m", 1700.0))
    is_high_altitude = location_id == "Los_Lirios_Arteaga" or elev_m >= 2000.0
    is_hyper_arid = location_id == "General_Cepeda" or (
        int(soil.get("water_retention_score", 2)) == 1 and elev_m < 1700.0
    )
    base_family = crop_info.get("familia_cultivo", "")

    if is_high_altitude:
        # En sierra y >= 2,000 msnm se descarta Sorgo y se priorizan cultivos tolerantes a heladas
        winter_primary = "Cebada_Forrajera_Precoz_Sierra_Fria"
        winter_alt = "Avena_Negra_Strigosa_Cobertura_Rustica"
        legume_pv = "Frijol_Negro_Altiplano"
        legume_pv_alt = "Frijol_Ayocote_Patol_Sierra"
        # Cultivos PV/anuales de baja demanda y tolerancia al frío para conservar agua sin usar Sorgo
        if base_family in {"Cebada_Grano", "Cebada_Forrajera"}:
            drought_pv = "Avena_Grano_Precoz_Temporal_Altura"
        elif base_family in {"Avena_Grano", "Avena_Forrajera"}:
            drought_pv = "Cebada_Grano_Precoz_Temporal_Altura"
        else:
            drought_pv = "Avena_Grano_Precoz_Temporal_Altura"
        drought_pv_alt = "Trigo_Harinero_Temporal_Valles_Altos" if base_family != "Trigo_Grano" else "Cebada_Grano_Precoz_Temporal_Altura"
        grain_or_cover_pv = "Maiz_Nativo_Elotes_Conicos" if base_family != "Maiz" else "Avena_Grano_Precoz_Temporal_Altura"
        perennial_legume = "Alfalfa_Semi_Latente_Valles_Templados"
    elif is_hyper_arid:
        winter_primary = "Avena_Negra_Strigosa_Cobertura_Rustica"
        winter_alt = "Cebada_Forrajera_Precoz_Sierra_Fria"
        legume_pv = "Frijol_Pinto_Centauro"
        legume_pv_alt = "Frijol_Pinto_Villa"
        if base_family in {"Sorgo_Forrajero", "Sorgo_Grano"}:
            drought_pv = "Girasol_Confitera_Polinizacion_Libre_Temporal"
        elif market_goal == "grano":
            drought_pv = "Sorgo_Grano_Precoz_Temporal"
        else:
            drought_pv = "Sorgo_Forrajero_Achicalado_Sudan_Multicorte"
        drought_pv_alt = "Frijol_Pinto_Centauro"
        grain_or_cover_pv = "Sorgo_Forrajero_Achicalado_Sudan_Multicorte" if base_family != "Sorgo_Forrajero" else "Maiz_Nativo_Raton"
        perennial_legume = "Alfalfa_Tolerante_Salinidad_Riego_Limitado"
    else:
        # Valles templados (UAAAN La Narro / Saltillo)
        winter_primary = "Avena_Forrajera_Precoz_Temporal_Cobertura"
        winter_alt = "Cebada_Forrajera_Precoz_Sierra_Fria"
        legume_pv = "Frijol_Pinto_Saltillo"
        legume_pv_alt = "Frijol_Negro_Altiplano"
        if base_family in {"Sorgo_Forrajero", "Sorgo_Grano"}:
            drought_pv = "Girasol_Confitera_Polinizacion_Libre_Temporal"
        elif market_goal == "grano":
            drought_pv = "Sorgo_Grano_Tolerante_Frio_Valles_Altos"
        else:
            drought_pv = "Sorgo_Forrajero_Tolerante_Frio_Valles_Altos"
        drought_pv_alt = "Frijol_Pinto_Saltillo"
        grain_or_cover_pv = "Maiz_Mejorado_VPL_Precoz_UAAAN_INIFAP" if base_family != "Maiz" else "Sorgo_Grano_Tolerante_Frio_Valles_Altos"
        perennial_legume = "Alfalfa_Semi_Latente_Valles_Templados"

    # Evitar repetir exactamente el mismo winter_primary si current_crop ya es esa cobertura invernal
    if current_crop == winter_primary:
        winter_primary, winter_alt = winter_alt, winter_primary
    if current_crop == legume_pv:
        legume_pv, legume_pv_alt = legume_pv_alt, legume_pv
    if current_crop == drought_pv:
        drought_pv = drought_pv_alt if drought_pv_alt != current_crop else legume_pv

    return {
        "winter_primary": winter_primary,
        "winter_alt": winter_alt,
        "legume_pv": legume_pv,
        "legume_pv_alt": legume_pv_alt,
        "drought_pv": drought_pv,
        "drought_pv_alt": drought_pv_alt,
        "grain_or_cover_pv": grain_or_cover_pv,
        "perennial_legume": perennial_legume,
        "is_high_altitude": "1" if is_high_altitude else "0",
        "is_hyper_arid": "1" if is_hyper_arid else "0",
    }


def _build_rotation_templates(
    location_id: str,
    current_crop: str,
    cultivos: dict[str, dict[str, Any]],
    soil: dict[str, Any] | None = None,
    market_goal: str = "grano",
) -> list[dict[str, Any]]:
    """
    Construye los 3 planes comparativos a 3 años (6 ciclos) adaptados a la parcela,
    respetando clima/altitud (>=2,000 msnm sin Sorgo) y `modo_en_kultiva`
    (frutales y perennes intercalados conservan la huerta activa los 3 años).
    """
    soil_ctx = soil or {"local_elevation_m": 2280.0 if location_id == "Los_Lirios_Arteaga" else 1760.0}
    crop_info = cultivos[current_crop]
    crop_label = crop_info["cultivo_label"]
    ciclo_norm = crop_info.get("ciclo_norm") or crop_info["ciclo_siembra"]
    modo_kultiva = crop_info.get("modo_en_kultiva", "Rotacion_Ciclica")
    base_family = crop_info.get("familia_cultivo", "")

    partners = _select_rotation_partners(location_id, soil_ctx, market_goal, current_crop, crop_info)
    winter_primary = partners["winter_primary"]
    winter_alt = partners["winter_alt"]
    legume_pv = partners["legume_pv"]
    drought_pv = partners["drought_pv"]
    grain_or_cover_pv = partners["grain_or_cover_pv"]
    perennial_legume = partners["perennial_legume"]
    is_high_altitude = partners["is_high_altitude"] == "1"
    is_hyper_arid = partners["is_hyper_arid"] == "1"

    # =========================================================================
    # MODO A: COBERTURA INTERCALADA PERENNE (Frutales Perennes, Nopal, Maguey)
    # Nunca sugiere arrancar la huerta en Años 2 y 3; intercala coberturas en callejones.
    # =========================================================================
    if modo_kultiva == "Cobertura_Intercalada_Perenne":
        plan_actual = {
            "plan_id": "plan_actual",
            "plan_name": f"Plan Actual (Huerta sin cobertura: {crop_label})",
            "strategy_focus": f"Huerta perenne de {crop_label} con callejones desnudos entre hileras durante los 3 años",
            "years": [
                {"year": 1, "pv": current_crop, "oi": "Barbecho_Suelo_Desnudo", "intercropped": False},
                {"year": 2, "pv": current_crop, "oi": "Barbecho_Suelo_Desnudo", "intercropped": False},
                {"year": 3, "pv": current_crop, "oi": "Barbecho_Suelo_Desnudo", "intercropped": False},
            ],
        }
        plan_conservacion = {
            "plan_id": "plan_conservacion_hidrica",
            "plan_name": "Plan Conservación Hídrica (Cobertura en Callejones)",
            "strategy_focus": (
                f"Mantiene activa tu huerta de {crop_label} los 3 años e intercala cobertura invernal de bajo consumo "
                f"en callejones para frenar evaporación y erosión"
            ),
            "years": [
                {"year": 1, "pv": current_crop, "oi": winter_primary, "intercropped": True},
                {"year": 2, "pv": current_crop, "oi": winter_alt, "intercropped": True},
                {"year": 3, "pv": current_crop, "oi": winter_primary, "intercropped": True},
            ],
        }
        # En Plan Regenerativo se mantiene el frutal perenne activo e intercala cobertura + leguminosas fijadoras en callejones
        plan_regenerativo = {
            "plan_id": "plan_regenerativo",
            "plan_name": "Plan Regenerativo (Callejones Vivos + Nitrógeno)",
            "strategy_focus": (
                f"Mantiene intacta tu huerta de {crop_label} los 3 años e intercala cobertura invernal y leguminosas "
                f"fijadoras de nitrógeno en los callejones entre hileras"
            ),
            "years": [
                {"year": 1, "pv": current_crop, "oi": winter_primary, "intercropped": True},
                {"year": 2, "pv": current_crop, "oi": winter_alt, "alley_pv": legume_pv, "intercropped": True},
                {
                    "year": 3,
                    "pv": current_crop,
                    "oi": winter_primary,
                    "alley_pv": partners["legume_pv_alt"],
                    "intercropped": True,
                },
            ],
        }
        return [plan_actual, plan_conservacion, plan_regenerativo]

    # =========================================================================
    # MODO B: ROTACIÓN CÍCLICA (Granos, Leguminosas, Forrajes, Hortalizas, Oleaginosas)
    # =========================================================================
    # 1. Plan Actual (Línea Base del Agricultor: monocultivo de current_crop durante 3 años)
    if ciclo_norm == "Todo_el_ano":
        actual_years = [
            {"year": 1, "pv": current_crop, "oi": current_crop},
            {"year": 2, "pv": current_crop, "oi": current_crop},
            {"year": 3, "pv": current_crop, "oi": current_crop},
        ]
        actual_focus = f"Monocultivo continuo de {crop_label} (Todo el año) durante los 3 años"
    elif ciclo_norm == "Otono-Invierno":
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

    # 2. Plan Conservación Hídrica (Mantiene current_crop en Año 1 y rota en Años 2 y 3 hacia mínimo consumo hídrico)
    if ciclo_norm == "Todo_el_ano":
        cons_y1 = {"year": 1, "pv": current_crop, "oi": current_crop}
        cons_y2 = {"year": 2, "pv": drought_pv, "oi": winter_primary}
        cons_y3 = {"year": 3, "pv": legume_pv, "oi": winter_alt}
    elif ciclo_norm == "Otono-Invierno":
        cons_y1 = {"year": 1, "pv": drought_pv, "oi": current_crop}
        cons_y2 = {"year": 2, "pv": legume_pv, "oi": winter_primary}
        cons_y3 = {"year": 3, "pv": drought_pv, "oi": winter_alt}
    else:
        cons_y1 = {"year": 1, "pv": current_crop, "oi": winter_primary}
        if base_family == "Frijol":
            cons_y2 = {"year": 2, "pv": drought_pv, "oi": winter_alt}
            cons_y3 = {"year": 3, "pv": current_crop, "oi": winter_primary}
        elif base_family in {"Sorgo_Forrajero", "Sorgo_Grano"}:
            cons_y2 = {"year": 2, "pv": legume_pv, "oi": winter_alt}
            cons_y3 = {"year": 3, "pv": drought_pv, "oi": winter_primary}
        else:
            cons_y2 = {"year": 2, "pv": drought_pv, "oi": winter_alt}
            cons_y3 = {"year": 3, "pv": legume_pv, "oi": winter_primary}

    plan_conservacion = {
        "plan_id": "plan_conservacion_hidrica",
        "plan_name": "Plan Conservación Hídrica",
        "strategy_focus": f"Año 1 con {crop_label} y rotación en Años 2–3 hacia cultivos de baja demanda hídrica y cobertura invernal",
        "years": [cons_y1, cons_y2, cons_y3],
    }

    # 3. Plan Regenerativo (Mantiene current_crop en Año 1 y alterna en Años 2 y 3 con leguminosas y cobertura continua)
    if ciclo_norm == "Todo_el_ano":
        reg_y1 = {"year": 1, "pv": current_crop, "oi": current_crop}
        reg_y2 = {"year": 2, "pv": grain_or_cover_pv, "oi": winter_primary}
        reg_y3 = {"year": 3, "pv": legume_pv, "oi": winter_alt}
    elif ciclo_norm == "Otono-Invierno":
        reg_y1 = {"year": 1, "pv": legume_pv, "oi": current_crop}
        reg_y2 = {"year": 2, "pv": grain_or_cover_pv, "oi": winter_alt}
        reg_y3 = {"year": 3, "pv": legume_pv, "oi": winter_primary}
    elif base_family == "Frijol":
        reg_y1 = {"year": 1, "pv": current_crop, "oi": winter_primary}
        reg_y2 = {"year": 2, "pv": grain_or_cover_pv, "oi": winter_alt}
        reg_y3 = {"year": 3, "pv": current_crop, "oi": winter_primary}
    elif base_family in {"Sorgo_Forrajero", "Sorgo_Grano"}:
        reg_y1 = {"year": 1, "pv": current_crop, "oi": winter_primary}
        reg_y2 = {"year": 2, "pv": legume_pv, "oi": winter_alt}
        reg_y3 = {
            "year": 3,
            "pv": legume_pv if is_hyper_arid else grain_or_cover_pv,
            "oi": winter_primary,
        }
    else:
        reg_y1 = {"year": 1, "pv": current_crop, "oi": winter_primary}
        reg_y2 = {"year": 2, "pv": legume_pv, "oi": winter_alt}
        if is_hyper_arid:
            reg_y3 = {"year": 3, "pv": drought_pv, "oi": winter_primary}
        elif is_high_altitude and float(crop_info.get("consumo_agua_mm", 450.0)) <= 450.0:
            # En sierra con cultivos base de bajo consumo, priorizar leguminosa anual + cobertura fría para conservar ahorro hídrico
            reg_y3 = {"year": 3, "pv": partners["legume_pv_alt"], "oi": winter_primary}
        else:
            reg_y3 = {"year": 3, "pv": perennial_legume, "oi": perennial_legume}

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
    alley_pv_id = year_spec.get("alley_pv")
    is_intercropped = bool(year_spec.get("intercropped", False))

    pv_crop = cultivos[pv_id]
    oi_crop = cultivos[oi_id]
    alley_pv_crop = cultivos[alley_pv_id] if alley_pv_id and alley_pv_id in cultivos else None

    is_perennial_orchard = pv_crop.get("modo_en_kultiva") == "Cobertura_Intercalada_Perenne"
    is_continuous_perennial = (
        not is_perennial_orchard
        and pv_id == oi_id
        and pv_id != "Barbecho_Suelo_Desnudo"
        and (pv_crop.get("ciclo_norm") == "Todo_el_ano" or str(pv_crop.get("ciclo_siembra", "")).startswith("Perenne"))
    )

    has_summer_cover = pv_id != "Barbecho_Suelo_Desnudo"
    has_winter_cover = oi_id != "Barbecho_Suelo_Desnudo"
    has_full_year_cover = has_summer_cover and has_winter_cover

    # Cada +1.0 °C incrementa la demanda hídrica de los cultivos en ~6%
    heat_water_factor = 1.0 + 0.06 * float(temp_increase_c)

    # 1. Cálculo de demanda hídrica efectiva (mm/ha)
    if is_continuous_perennial:
        pv_water_raw = float(pv_crop["consumo_agua_mm"]) * 0.60 * heat_water_factor
        oi_water_raw = float(oi_crop["consumo_agua_mm"]) * 0.40 * heat_water_factor
        alley_water_raw = 0.0
    elif is_perennial_orchard:
        pv_water_raw = float(pv_crop["consumo_agua_mm"]) * heat_water_factor
        # La cobertura en callejones ocupa ~35% de la superficie del suelo entre hileras
        oi_water_raw = (float(oi_crop["consumo_agua_mm"]) * 0.35 * heat_water_factor) if has_winter_cover else 0.0
        alley_water_raw = (
            float(alley_pv_crop["consumo_agua_mm"]) * 0.25 * heat_water_factor if alley_pv_crop is not None else 0.0
        )
    else:
        pv_water_raw = float(pv_crop["consumo_agua_mm"]) * heat_water_factor
        oi_water_raw = float(oi_crop["consumo_agua_mm"]) * heat_water_factor
        alley_water_raw = 0.0

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
        monoculture_runoff_loss_mm += max(0.0, float(soil["pendiente_pct"]) - 3.5) * 6.0
    if tillage_mode == "convencional" and int(soil["erosion_risk_score"]) >= 3 and not has_full_year_cover:
        monoculture_runoff_loss_mm += 18.0 * heat_water_factor

    tillage_mulch_bonus_mm = 22.0 if tillage_mode == "conservacion" else 0.0

    if is_continuous_perennial:
        is_high_water_perennial = float(pv_crop["consumo_agua_mm"]) >= 600.0
        perennial_evap_surcharge_mm = (
            {1: 115.0, 2: 95.0, 3: 75.0}.get(water_ret_score, 95.0) * heat_water_factor
            if is_high_water_perennial
            else {1: 45.0, 2: 35.0, 3: 25.0}.get(water_ret_score, 35.0) * heat_water_factor
        )
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
    elif is_perennial_orchard and has_full_year_cover:
        winter_rain_captured_mm = min((oi_water_raw + alley_water_raw) * 0.75, climate["rain_adj_oi_mm"] * 0.85)
        mulch_moisture_credit_mm = 48.0 + 14.0 * water_ret_score + tillage_mulch_bonus_mm
        net_alley_delta = (oi_water_raw + alley_water_raw) - winter_rain_captured_mm - mulch_moisture_credit_mm
        effective_water_demand_mm = max(
            pv_water_raw * 0.78,
            pv_water_raw + net_alley_delta + monoculture_runoff_loss_mm,
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

    high_demand_temporal_penalty = 0.0
    primary_water_mm = float(pv_crop["consumo_agua_mm"]) if has_summer_cover else float(oi_crop["consumo_agua_mm"])
    if irrigation_mode == "temporal" and primary_water_mm >= 500.0:
        if is_continuous_perennial:
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

    # 4. Semáforo de Plagas (penalización por monocultivo sin diversificación: +35% Año 2, +70% Año 3)
    if consecutive_monoculture_years == 0:
        is_legume_rotation = (
            int(pv_crop["fija_nitrogeno_bin"]) == 1
            or int(oi_crop["fija_nitrogeno_bin"]) == 1
            or (alley_pv_crop is not None and int(alley_pv_crop["fija_nitrogeno_bin"]) == 1)
        )
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
    if is_continuous_perennial or is_perennial_orchard:
        base_net_income_ha = float(pv_crop["ingreso_neto_ha_mxn"])
        if is_perennial_orchard and not has_winter_cover:
            # Limpia mecánica/herbicida en callejones desnudos
            base_net_income_ha -= 1200.0
    else:
        base_net_income_ha = float(pv_crop["ingreso_neto_ha_mxn"]) + float(oi_crop["ingreso_neto_ha_mxn"])

    n_fixing_cycles_this_year = (
        int(pv_crop["fija_nitrogeno_bin"])
        + (int(oi_crop["fija_nitrogeno_bin"]) if not is_continuous_perennial else 0)
        + (int(alley_pv_crop["fija_nitrogeno_bin"]) if alley_pv_crop is not None else 0)
    )
    has_carryover_n = (
        cumulative_n_fixed_cycles > 0
        and has_summer_cover
        and int(pv_crop["fija_nitrogeno_bin"]) == 0
        and (alley_pv_crop is None or int(alley_pv_crop["fija_nitrogeno_bin"]) == 0)
    )

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

    pv_label = pv_crop["cultivo_label"]
    if is_perennial_orchard and alley_pv_crop is not None:
        pv_label = f"{pv_crop['cultivo_label']} + {alley_pv_crop['cultivo_label']} (en callejones)"

    if is_perennial_orchard and not has_winter_cover:
        oi_label = "Callejones desnudos (sin cobertura)"
    elif is_perennial_orchard and is_intercropped and has_winter_cover:
        oi_label = f"{oi_crop['cultivo_label']} (cobertura en callejones)"
    else:
        oi_label = oi_crop["cultivo_label"]

    return {
        "year": int(year_spec["year"]),
        "pv_crop_id": pv_id,
        "pv_crop_label": pv_label,
        "oi_crop_id": oi_id,
        "oi_crop_label": oi_label,
        "intercropped": is_intercropped,
        "alley_pv_crop_id": alley_pv_id,
        "catalog_water_mm": round(pv_water_raw + oi_water_raw + alley_water_raw, 1),
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
    current_crop_info: dict[str, Any],
) -> list[str]:
    municipio = soil["municipio"].replace("_", " ")
    tipo_suelo = soil["tipo_suelo_label"]
    pendiente = soil["pendiente_pct"]
    irrig_label = "temporal (secano)" if irrigation_mode == "temporal" else "riego de auxilio"
    categoria = current_crop_info.get("categoria_siap", "")
    if categoria in {"Hortalizas", "Frutales_Perennes"}:
        goal_label = "comercialización hortofrutícola"
    else:
        goal_label = "grano comercial" if market_goal == "grano" else "forraje ganadero"
    current_crop_label = current_crop_info["cultivo_label"]

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
            f"Validación comercial y agronómica: Verifique abasto local de semilla o planta certificada para {crops_str} "
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
    current_ciclo = current_crop_info.get("ciclo_norm") or current_crop_info["ciclo_siembra"]
    is_orchard = current_crop_info.get("modo_en_kultiva") == "Cobertura_Intercalada_Perenne"
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
        if is_orchard:
            return (
                f"Con base en 10 años de datos NASA POWER (MERRA-2/IMERG) y MODIS MOD13Q1 en {zona}, "
                f"{rain_clause}, mantener {current_crop_label} con callejones desnudos durante 3 años en {hectares:.1f} ha "
                f"expone los entre-surcos 18 meses a evaporación y erosión "
                f"(en los {modis_alert_months} meses críticos/año detectados por MODIS NDVI), "
                f"eleva +70% la presión de plagas hacia el Año 3 ({plan_metrics['years'][2]['effective_pest_days']:.1f} días equivalentes){fert_warn} "
                f"y coloca el diagnóstico de sequía en {plan_seq_phrase}."
            )
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

    action_phrase = (
        f"mantener activa la huerta de {current_crop_label} los 3 años e intercalar {crops_str} en los callejones"
        if is_orchard
        else f"sembrar {current_crop_label} en el Año 1 y rotar con {crops_str}"
    )

    return (
        f"Con base en 10 años de registros satelitales NASA POWER y MODIS NDVI en {zona}, "
        f"{rain_clause}, mientras el manejo sin cobertura de {current_crop_label} entra en {base_seq_phrase} de sequía "
        f"y {base_pla_phrase} de plagas, {action_phrase} en {hectares:.1f} ha "
        f"{water_clause}, protege el suelo los 36 meses "
        f"(mitigando {modis_alert_3y} meses acumulados de alerta por suelo desnudo/estrés en MODIS NDVI) "
        f"y genera ${plan_metrics['ingreso_neto_total_mxn']:,.0f} MXN netos "
        f"({'+' if income_diff >= 0 else ''}${income_diff:,.0f} MXN vs. manejo base de {current_crop_label}).{fert_savings_clause}"
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
    main_concern: str | list[str] = "sequia",
) -> dict[str, Any]:
    """
    Ejecuta el motor de simulación "What-If" de Kultiva a 3 años (6 ciclos)
    para la parcela y el cultivo/familia seleccionados contra el catálogo oficial de 168 variedades,
    aceptando calibración manual de suelo y prácticas de fertilización / manejo de rastrojo.
    """
    climatology, cultivos, suelos = _load_datasets()

    if location_id not in climatology["locations"] or location_id not in suelos:
        valid_ids = sorted(suelos.keys())
        raise ValueError(f"location_id '{location_id}' no válido. Opciones: {valid_ids}")

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
    raw_concerns = main_concern if isinstance(main_concern, (list, tuple, set)) else str(main_concern or "sequia").split(",")
    concerns: list[str] = []
    for item in raw_concerns:
        key = str(item or "").strip().lower()
        if key in CONCERN_LABELS and key not in concerns:
            concerns.append(key)
    if not concerns:
        concerns = ["sequia"]

    loc_clim_months = climatology["locations"][location_id]["months"]
    soil, is_custom_soil, base_elevation_m = _apply_soil_override(suelos[location_id], soil_override)
    climate = _compute_parcel_climate_metrics(loc_clim_months, rain_reduction_pct, temp_increase_c)

    requested_crop = str(current_crop or "Maiz_Grano").strip()
    resolved_crop_id, selection_mode = _resolve_crop_selection(
        requested_crop=requested_crop,
        cultivos=cultivos,
        location_id=location_id,
        soil=soil,
        irrigation_mode=irrigation_mode,
        market_goal=market_goal,
        concerns=concerns,
        custom_crop_name=custom_crop_name,
        custom_crop_water_tier=custom_crop_water_tier,
    )
    current_crop_info = cultivos[resolved_crop_id]

    w_water, w_profit, w_nitrogen = _normalize_weights(weight_water, weight_profit, weight_nitrogen)
    w_water_adj = w_water + (0.18 if "sequia" in concerns else 0.0)
    w_nitrogen_adj = w_nitrogen + (0.18 if "suelo" in concerns else 0.0)
    w_water, w_profit, w_nitrogen = _normalize_weights(w_water_adj, w_profit, w_nitrogen_adj)

    templates = _build_rotation_templates(
        location_id=location_id,
        current_crop=resolved_crop_id,
        cultivos=cultivos,
        soil=soil,
        market_goal=market_goal,
    )
    evaluated_plans: list[dict[str, Any]] = []

    for tpl in templates:
        yearly_results: list[dict[str, Any]] = []
        prev_main_crop: str | None = None
        consec_mono = 0
        cum_n_cycles = 0
        is_baseline_plan = tpl["plan_id"] == "plan_actual"

        for y_spec in tpl["years"]:
            main_crop = y_spec["pv"] if y_spec["pv"] != "Barbecho_Suelo_Desnudo" else y_spec["oi"]
            is_intercropped_year = bool(y_spec.get("intercropped", False))
            if is_intercropped_year and not is_baseline_plan:
                # La cobertura intercalada en callejones rompe el monocultivo desnudo
                consec_mono = 0
            elif prev_main_crop is not None and main_crop == prev_main_crop:
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

    max_net_ha_3a = max(p["ingreso_neto_ha_3a_mxn"] for p in evaluated_plans)
    profit_ref_3a = max(92000.0, max_net_ha_3a * 1.08)

    for plan in evaluated_plans:
        water_saved_mm = baseline_water_mm - plan["demanda_agua_efectiva_3a_mm"]
        plan_water_m3 = round(plan["demanda_agua_efectiva_3a_mm"] * 10.0 * hectares, 1)
        plan["consumo_agua_total_3a_m3"] = plan_water_m3
        plan["ahorro_agua_m3"] = round(water_saved_mm * 10.0 * hectares, 1)
        plan["consumo_agua_litros"] = int(round(plan_water_m3 * 1000.0))
        plan["ahorro_agua_litros"] = int(round((baseline_water_m3 - plan_water_m3) * 1000.0))

        avg_drought_stress = sum(y["drought_stress_index"] for y in plan["years"]) / 3.0
        light_water_bonus = {"VERDE": 14.0, "AMARILLO": 0.0, "ROJO": -18.0}[plan["semaforo_sequia"]]
        water_savings_bonus = min(28.0, max(-10.0, (water_saved_mm / 650.0) * 28.0))
        water_score = max(
            5.0,
            min(100.0, 100.0 - max(0.0, avg_drought_stress - 55.0) * 1.05 + water_savings_bonus + light_water_bonus),
        )

        profit_raw = (plan["ingreso_neto_ha_3a_mxn"] / profit_ref_3a) * 100.0
        pest_frost_penalty = (
            (8.0 if plan["semaforo_plagas"] == "ROJO" else 3.0 if plan["semaforo_plagas"] == "AMARILLO" else 0.0)
            + (8.0 if plan["semaforo_heladas"] == "ROJO" else 3.0 if plan["semaforo_heladas"] == "AMARILLO" else 0.0)
        )
        profit_score = max(5.0, min(100.0, profit_raw - pest_frost_penalty))

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

        active_crops = [y["pv_crop_id"] for y in plan["years"] if y["pv_crop_id"] != "Barbecho_Suelo_Desnudo"] + [
            y["oi_crop_id"] for y in plan["years"] if y["oi_crop_id"] != "Barbecho_Suelo_Desnudo"
        ]
        if market_goal == "forraje":
            forage_ratio = sum(1 for c in active_crops if _is_forage_crop(cultivos[c])) / max(1, len(active_crops))
            market_alignment_bonus = (forage_ratio - 0.35) * 12.0
        else:
            grain_count = sum(1 for c in active_crops if _is_grain_or_commercial_crop(cultivos[c]))
            market_alignment_bonus = 2.0 if grain_count >= 2 else 0.0

        concern_alignment_bonus = 0.0
        for c in concerns:
            if c == "sequia":
                if plan["plan_id"] == "plan_conservacion_hidrica":
                    concern_alignment_bonus += 4.2
                elif plan["plan_id"] == "plan_regenerativo":
                    concern_alignment_bonus += 1.8
                else:
                    concern_alignment_bonus -= 3.0
            elif c == "suelo":
                if plan["plan_id"] == "plan_regenerativo":
                    concern_alignment_bonus += 4.8
                elif plan["plan_id"] == "plan_conservacion_hidrica":
                    concern_alignment_bonus += 2.0
                else:
                    concern_alignment_bonus -= 3.5
            elif c == "plagas":
                if plan["semaforo_plagas"] == "VERDE":
                    concern_alignment_bonus += 3.8 if plan["plan_id"] == "plan_regenerativo" else 3.2
                elif plan["semaforo_plagas"] == "ROJO":
                    concern_alignment_bonus -= 4.0
            elif c == "heladas":
                if plan["semaforo_heladas"] == "VERDE" and months_bare == 0:
                    concern_alignment_bonus += 3.8
                elif months_bare == 0:
                    concern_alignment_bonus += 2.0
                else:
                    concern_alignment_bonus -= 3.0
        if len(concerns) > 1:
            concern_alignment_bonus *= 0.75

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
            current_crop_info=current_crop_info,
        )

    ranked = sorted(evaluated_plans, key=lambda p: p["suitability_score"], reverse=True)
    recommended = ranked[0]

    return {
        "location_id": location_id,
        "zona_label": soil["zona_label"],
        "municipio": soil["municipio"],
        "hectares": hectares,
        "requested_crop": requested_crop,
        "selection_mode": selection_mode,
        "current_crop": resolved_crop_id,
        "current_crop_label": current_crop_info["cultivo_label"],
        "current_crop_cycle_label": current_crop_info["ciclo_label"],
        # Metadatos oficiales de la variedad resuelta (PASO 3.5)
        "cultivo": current_crop_info["cultivo"],
        "familia_cultivo": current_crop_info["familia_cultivo"],
        "nombre_comun": current_crop_info["nombre_comun"],
        "categoria_siap": current_crop_info["categoria_siap"],
        "clasificacion_oficial": current_crop_info["clasificacion_oficial"],
        "consumo_agua_mm": current_crop_info["consumo_agua_mm"],
        "dias_madurez": current_crop_info["dias_madurez"],
        "fuente_oficial": current_crop_info["fuente_oficial"],
        "modo_en_kultiva": current_crop_info.get("modo_en_kultiva", "Rotacion_Ciclica"),
        "beneficio_principal": current_crop_info.get("beneficio_principal", ""),
        "rain_reduction_pct": rain_reduction_pct,
        "temp_increase_c": temp_increase_c,
        "irrigation_mode": irrigation_mode,
        "market_goal": market_goal,
        "fertilizer_type": fertilizer_type,
        "fertilizer_label": FERTILIZER_LABELS[fertilizer_type],
        "tillage_mode": tillage_mode,
        "tillage_label": TILLAGE_LABELS[tillage_mode],
        "main_concern": concerns[0] if len(concerns) == 1 else concerns,
        "main_concerns": concerns,
        "main_concern_label": " · ".join(CONCERN_LABELS[c] for c in concerns),
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
            "main_concern": concerns[0] if len(concerns) == 1 else concerns,
            "main_concerns": concerns,
            "main_concern_label": " · ".join(CONCERN_LABELS[c] for c in concerns),
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

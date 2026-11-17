from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field

from src.agroshift_engine import (
    get_official_catalog_payload,
    simulate_all_168_crops,
    simulate_scenarios,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
STATIC_DIR = BASE_DIR / "static"
MONTHLY_CSV_PATH = DATA_DIR / "agroshift_parcelas_monthly.csv"

app = FastAPI(title="Kultiva API", version="2.1")


class SimulateRequest(BaseModel):
    location_id: str
    hectares: float = Field(default=10.0, gt=0)
    weight_water: float = Field(default=0.33, ge=0)
    weight_profit: float = Field(default=0.33, ge=0)
    weight_nitrogen: float = Field(default=0.34, ge=0)
    rain_reduction_pct: float = Field(default=0.0, ge=0, le=0.8)
    temp_increase_c: float = Field(default=0.0, ge=0.0, le=3.0)
    irrigation_mode: str = Field(default="temporal")
    market_goal: str = Field(default="grano")
    current_crop: str | None = Field(default=None)
    familia_cultivo: str | None = Field(default=None)
    custom_crop_name: str | None = Field(default=None)
    custom_crop_water_tier: str = Field(default="medio")
    soil_override: dict[str, Any] | None = Field(default=None)
    fertilizer_type: str = Field(default="quimico")
    tillage_mode: str = Field(default="convencional")
    main_concern: str | list[str] = Field(default="sequia")
    selected_problems: list[str] | None = Field(default=None)


def _read_json(name: str) -> Any:
    with (DATA_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_monthly_history_by_location() -> dict[str, list[dict[str, Any]]]:
    """Read agroshift_parcelas_monthly.csv and return chronological 2016-2026 series grouped by location_id."""
    history: dict[str, list[dict[str, Any]]] = {}
    with MONTHLY_CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc_id = row["location_id"]
            yr = int(row["year"])
            mo = int(row["month"])
            record = {
                "date_label": f"{yr}-{mo:02d}",
                "year": yr,
                "month": mo,
                "lluvia_mm": round(float(row["prectotcorr_sum"]), 2),
                "ndvi_mean": round(float(row["ndvi_mean"]), 4),
                "temp_max": round(float(row["t2m_max_mean"]), 2),
                "soil_moisture_avg": round(float(row["soil_moisture_avg_mean"]), 4),
                "bare_soil_or_stress_alert": int(row["bare_soil_or_stress_alert"]),
            }
            history.setdefault(loc_id, []).append(record)

    for loc_id, rows in history.items():
        rows.sort(key=lambda r: (r["year"], r["month"]))
    return history


@app.get("/api/init")
def api_init() -> dict[str, Any]:
    catalog = get_official_catalog_payload()
    return {
        "suelos": _read_json("suelos_coahuila_clean.json"),
        "cultivos": catalog["cultivos"],
        "familias_cultivo": catalog["familias_cultivo"],
        "catalogo_agrupado": catalog["catalogo_agrupado"],
        "climatology": _read_json("agroshift_climatology_12m.json"),
        "history_by_location": load_monthly_history_by_location(),
    }


@app.get("/api/history/{location_id}")
def api_history(location_id: str) -> dict[str, Any]:
    history = load_monthly_history_by_location()
    if location_id not in history:
        raise HTTPException(
            status_code=404,
            detail=f"location_id '{location_id}' no encontrado. Opciones: {sorted(history.keys())}",
        )
    series = history[location_id]
    return {
        "location_id": location_id,
        "total_months": len(series),
        "period_start": series[0]["date_label"] if series else None,
        "period_end": series[-1]["date_label"] if series else None,
        "series": series,
    }


@app.post("/api/simulate")
def api_simulate(req: SimulateRequest) -> dict[str, Any]:
    try:
        effective_crop = req.current_crop or req.familia_cultivo or "Maiz_Grano"
        return simulate_scenarios(
            location_id=req.location_id,
            hectares=req.hectares,
            weight_water=req.weight_water,
            weight_profit=req.weight_profit,
            weight_nitrogen=req.weight_nitrogen,
            rain_reduction_pct=req.rain_reduction_pct,
            temp_increase_c=req.temp_increase_c,
            irrigation_mode=req.irrigation_mode,
            market_goal=req.market_goal,
            current_crop=effective_crop,
            custom_crop_name=req.custom_crop_name,
            custom_crop_water_tier=req.custom_crop_water_tier,
            soil_override=req.soil_override,
            fertilizer_type=req.fertilizer_type,
            tillage_mode=req.tillage_mode,
            main_concern=req.selected_problems if req.selected_problems else req.main_concern,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _estimate_wrapped_row_height(texts_and_widths: list[tuple[str, int]], min_h: float = 26.0, line_h: float = 14.2) -> float:
    max_lines = 1
    for txt, col_w in texts_and_widths:
        s = str(txt or "")
        if not s:
            continue
        usable = max(12, col_w - 3)
        total = 0
        for part in s.splitlines() or [""]:
            total += max(1, (len(part) + usable - 1) // usable)
        if total > max_lines:
            max_lines = total
    return max(min_h, min(140.0, max_lines * line_h + 8.0))


def _build_excel_workbook(sim: dict[str, Any], rows_168: list[dict[str, Any]]) -> bytes:
    wb = Workbook()

    header_fill = PatternFill(start_color="0F5132", end_color="0F5132", fill_type="solid")
    sub_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    guide_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    best_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    pos_water_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    neg_water_fill = PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")

    light_fills = {
        "VERDE": PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
        "AMARILLO": PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
        "ROJO": PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
    }
    light_fonts = {
        "VERDE": Font(name="Calibri", size=10, bold=True, color="166534"),
        "AMARILLO": Font(name="Calibri", size=10, bold=True, color="92400E"),
        "ROJO": Font(name="Calibri", size=10, bold=True, color="991B1B"),
    }

    banner_font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    section_font = Font(name="Calibri", size=11, bold=True, color="0F5132")
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="Calibri", size=10, color="0F172A")
    bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
    muted_font = Font(name="Calibri", size=9, color="64748B")
    guide_font = Font(name="Calibri", size=9, italic=True, color="334155")
    pos_font = Font(name="Calibri", size=10, bold=True, color="166534")
    neg_font = Font(name="Calibri", size=10, bold=True, color="991B1B")

    thin_side = Side(style="thin", color="CBD5E1")
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    ctx = sim["parcel_context"]
    weights = sim.get("normalized_weights", {})
    w_agua = int(round(float(weights.get("weight_water", 0.33)) * 100))
    w_prof = int(round(float(weights.get("weight_profit", 0.33)) * 100))
    w_nit = int(round(float(weights.get("weight_nitrogen", 0.34)) * 100))
    regimen_label = "Riego / Riego de Auxilio" if sim["irrigation_mode"] == "riego" else "Solo Temporal (secano)"
    rain_pct = int(round(float(sim.get("rain_reduction_pct", 0.0)) * 100))
    rain_pct_str = "Lluvia histórica normal (0%)" if rain_pct == 0 else f"Sequía -{rain_pct}%"
    muni_clean = str(sim["municipio"]).replace("_", " ")
    soil_tag = " (Calibrado manual)" if sim.get("is_custom_soil") else " (Perfil regional)"

    cnt_muy_viable = sum(1 for r in rows_168 if str(r.get("estado_viabilidad", "")).startswith("✅"))
    cnt_con_manejo = sum(1 for r in rows_168 if str(r.get("estado_viabilidad", "")).startswith("⚠️"))
    cnt_alto_riesgo = sum(1 for r in rows_168 if str(r.get("estado_viabilidad", "")).startswith("❌"))

    # =========================================================================
    # HOJA 1 (PRINCIPAL): Evaluacion_168_Cultivos
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Evaluacion_168_Cultivos"

    ws1["A1"] = "KULTIVA · EVALUACIÓN DE LOS 168 CULTIVOS OFICIALES PARA TU PARCELA (COAHUILA)"
    ws1["A1"].font = banner_font
    ws1["A1"].fill = header_fill
    ws1["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.merge_cells("A1:T1")
    ws1.row_dimensions[1].height = 30

    # Bloque Superior (Filas 2 a 6): Ficha de Parcela, Decisiones y Resumen Rápido
    card_rows_1 = [
        (
            "Parcela / Municipio",
            f"{sim['zona_label']} ({muni_clean})",
            "Altitud",
            f"{int(round(float(ctx['local_elevation_m']))):,} msnm",
            "Suelo y % MO",
            f"{ctx['tipo_suelo_label']} ({ctx['textura_label']}) · MO {ctx['materia_organica_pct']}% · Pend. {ctx['pendiente_pct']}%{soil_tag}",
            "Superficie",
            f"{float(sim['hectares']):.1f} ha",
        ),
        (
            "Cultivo Actual",
            f"{sim['nombre_comun']} ({sim['familia_cultivo'].replace('_', ' ')})",
            "Régimen Hídrico",
            regimen_label,
            "Fertilizante / Labranza",
            f"{sim['fertilizer_label']} · {sim['tillage_label']}",
            "Destino",
            sim["market_goal"].capitalize(),
        ),
        (
            "Preocupaciones",
            sim["main_concern_label"],
            "Clima Simulado",
            f"{ctx['annual_simulated_rain_mm']} mm/año ({rain_pct_str}) · +{sim['temp_increase_c']:.1f} °C",
            "Prioridades Elegidas",
            f"Agua {w_agua}% · Ganancia {w_prof}% · Suelo/N {w_nit}%",
            "Fuente Base",
            sim["fuente_oficial"],
        ),
    ]
    for r_num, (k1, v1, k2, v2, k3, v3, k4, v4) in enumerate(card_rows_1, start=2):
        blocks = [
            ((1, 2), k1, True),
            ((3, 5), v1, False),
            ((6, 6), k2, True),
            ((7, 8), v2, False),
            ((9, 10), k3, True),
            ((11, 15), v3, False),
            ((16, 16), k4, True),
            ((17, 20), v4, False),
        ]
        for (c_start, c_end), val, is_lbl in blocks:
            cell = ws1.cell(row=r_num, column=c_start, value=val)
            cell.font = bold_font if is_lbl else body_font
            if is_lbl:
                cell.fill = sub_fill
            if c_end > c_start:
                ws1.merge_cells(start_row=r_num, start_column=c_start, end_row=r_num, end_column=c_end)
            for c_i in range(c_start, c_end + 1):
                mc = ws1.cell(row=r_num, column=c_i)
                mc.border = cell_border
                mc.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True)
                if is_lbl:
                    mc.fill = sub_fill
        ws1.row_dimensions[r_num].height = 24

    # Fila 5: Resumen rápido del catálogo (cuántos de 168 son Muy Viables / Con Manejo / Alto Riesgo)
    ws1.cell(row=5, column=1, value="Resumen Catálogo (168)").font = bold_font
    ws1.merge_cells("A5:B5")
    for c_i in (1, 2):
        ws1.cell(row=5, column=c_i).fill = sub_fill
        ws1.cell(row=5, column=c_i).border = cell_border
        ws1.cell(row=5, column=c_i).alignment = Alignment(vertical="center", horizontal="left")

    summary_pills = [
        (3, 6, f"✅ Muy Viables en tu Parcela: {cnt_muy_viable} de 168", light_fills["VERDE"], light_fonts["VERDE"]),
        (7, 11, f"⚠️ Viables con Manejo / Cuidados: {cnt_con_manejo} de 168", light_fills["AMARILLO"], light_fonts["AMARILLO"]),
        (12, 16, f"❌ Alto Riesgo de Pérdida: {cnt_alto_riesgo} de 168", light_fills["ROJO"], light_fonts["ROJO"]),
        (17, 20, "Comparado vs. Plan Actual + Top 5 Rotaciones en Hoja 2", guide_fill, guide_font),
    ]
    for c_start, c_end, val, fill_obj, font_obj in summary_pills:
        c0 = ws1.cell(row=5, column=c_start, value=val)
        c0.font = font_obj
        ws1.merge_cells(start_row=5, start_column=c_start, end_row=5, end_column=c_end)
        for c_i in range(c_start, c_end + 1):
            mc = ws1.cell(row=5, column=c_i)
            mc.fill = fill_obj
            mc.border = cell_border
            mc.alignment = Alignment(vertical="center", horizontal="center" if c_start < 17 else "left", wrap_text=True)
    ws1.row_dimensions[5].height = 24

    # Fila 6: Guía de lectura rápida + Fila 7 separador
    ws1.cell(
        row=6,
        column=1,
        value="Cómo leer esta tabla: Cada fila muestra qué pasaría en tu parcela si siembras ese cultivo durante 3 años frente a seguir con tu cultivo actual. Usa los filtros de la fila 8 para filtrar por Viabilidad, Agua o Riesgo.",
    )
    ws1.merge_cells("A6:T6")
    for c_i in range(1, 21):
        mc = ws1.cell(row=6, column=c_i)
        mc.fill = guide_fill
        mc.font = guide_font
        mc.border = cell_border
        mc.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True)
    ws1.row_dimensions[6].height = 22
    ws1.row_dimensions[7].height = 10

    # Fila 8: Encabezados de Tabla Principal (congelados + autofiltro)
    headers_168 = [
        "Posición (#)",
        "Viabilidad en tu Parcela",
        "Prob. de Supervivencia / Éxito (%)",
        "Cultivo y Variedad Oficial",
        "Categoría / Grupo",
        "Agua que Ahorras en 3 Años (m³)",
        "Agua que Ahorras (Litros)",
        "Agua Total que Necesita en 3 Años (m³)",
        "Ganancia Neta Estimada en 3 Años (MXN)",
        "Dinero Extra vs. tu Cultivo Actual (MXN)",
        "Ahorro en Fertilizante (MXN)",
        "¿Fija Nitrógeno?",
        "Meses con Suelo Protegido (de 36)",
        "Riesgo Sequía",
        "Riesgo Heladas",
        "Riesgo Plagas",
        "¿Qué pasaría si lo siembras en tu parcela?",
        "Zonas Recomendadas en Coahuila",
        "Respaldo Científico Oficial",
        "ID Técnico (Referencia)",
    ]
    header_row_168 = 8
    for col_i, h in enumerate(headers_168, start=1):
        c = ws1.cell(row=header_row_168, column=col_i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = cell_border
    ws1.row_dimensions[header_row_168].height = 36

    widths_168 = [12, 28, 17, 42, 30, 19, 19, 19, 21, 22, 18, 13, 17, 13, 13, 13, 64, 38, 36, 30]
    for r_offset, item in enumerate(rows_168, start=header_row_168 + 1):
        cat_grp = f"{item.get('categoria_label', item['categoria_siap'].replace('_', ' '))} · {item.get('familia_label', item['familia_cultivo'].replace('_', ' '))}"
        ahorro_m3 = round(float(item["ahorro_agua_vs_actual_m3"]), 1)
        diff_mxn = round(float(item["diferencia_dinero_vs_actual_mxn"]), 2)
        viab_txt = str(item.get("estado_viabilidad", ""))
        diag_txt = str(item.get("diagnostico_agricultor") or item.get("resumen_escenario", ""))

        row_vals = [
            int(item["ranking"]),
            viab_txt,
            int(item.get("probabilidad_supervivencia_pct", round(float(item["suitability_score"])))),
            item["nombre_comun"],
            cat_grp,
            ahorro_m3,
            int(item["ahorro_agua_vs_actual_litros"]),
            round(float(item["agua_consumida_3a_m3"]), 1),
            round(float(item["utilidad_neta_3a_mxn"]), 2),
            diff_mxn,
            round(float(item["ahorro_fertilizante_3a_mxn"]), 2),
            item.get("fija_nitrogeno", "No"),
            int(item["meses_suelo_protegido_36"]),
            item["semaforo_sequia"],
            item["semaforo_heladas"],
            item["semaforo_plagas"],
            diag_txt,
            item["municipios_coahuila"],
            item["fuente_oficial"],
            item["cultivo"],
        ]

        is_top5 = item["ranking"] <= 5
        for col_i, val in enumerate(row_vals, start=1):
            c = ws1.cell(row=r_offset, column=col_i, value=val)
            c.border = cell_border
            c.font = bold_font if (is_top5 and col_i in (1, 4)) else body_font
            c.alignment = Alignment(
                vertical="center",
                wrap_text=col_i in (2, 4, 5, 17, 18, 19),
                horizontal="center" if col_i in (1, 3, 12, 13, 14, 15, 16) else "left",
            )
            if is_top5:
                c.fill = sub_fill
            elif r_offset % 2 == 0:
                c.fill = zebra_fill

            if col_i == 2:
                if viab_txt.startswith("✅"):
                    c.fill = light_fills["VERDE"]
                    c.font = light_fonts["VERDE"]
                elif viab_txt.startswith("⚠️"):
                    c.fill = light_fills["AMARILLO"]
                    c.font = light_fonts["AMARILLO"]
                elif viab_txt.startswith("❌"):
                    c.fill = light_fills["ROJO"]
                    c.font = light_fonts["ROJO"]
            elif col_i == 3:
                c.number_format = '0"%"'
                c.font = bold_font
            elif col_i in (6, 7):
                c.number_format = "+#,##0;-#,##0;0"
                c.alignment = Alignment(horizontal="right", vertical="center")
                if ahorro_m3 >= 0:
                    c.font = pos_font
                    if not is_top5:
                        c.fill = pos_water_fill
                else:
                    c.font = neg_font
                    if not is_top5:
                        c.fill = neg_water_fill
            elif col_i == 8:
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i in (9, 11):
                c.number_format = "$#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i == 10:
                c.number_format = "+$#,##0;-$#,##0;$0"
                c.alignment = Alignment(horizontal="right", vertical="center")
                c.font = pos_font if diff_mxn > 0 else (neg_font if diff_mxn < 0 else body_font)
            elif col_i in (14, 15, 16) and val in light_fills:
                c.fill = light_fills[val]
                c.font = light_fonts[val]
            elif col_i == 20:
                c.font = muted_font

        ws1.row_dimensions[r_offset].height = _estimate_wrapped_row_height(
            [(diag_txt, 64), (item["nombre_comun"], 42), (item["municipios_coahuila"], 38), (item["fuente_oficial"], 36)],
            min_h=28.0,
        )

    ws1.auto_filter.ref = f"A{header_row_168}:T{header_row_168 + len(rows_168)}"
    ws1.freeze_panes = f"A{header_row_168 + 1}"
    for col_i, w in enumerate(widths_168, start=1):
        ws1.column_dimensions[get_column_letter(col_i)].width = w

    # =========================================================================
    # HOJA 2: Top_5_Rotaciones_3_Anos
    # =========================================================================
    ws2 = wb.create_sheet(title="Top_5_Rotaciones_3_Anos")
    ws2["A1"] = "Kultiva · Comparativa Plan Actual vs. Top 5 Rotaciones a 3 Años (Coahuila)"
    ws2["A1"].font = banner_font
    ws2["A1"].fill = header_fill
    ws2["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws2.merge_cells("A1:S1")
    ws2.row_dimensions[1].height = 28

    meta_rows_2 = [
        ("Parcela / Municipio", f"{sim['zona_label']} ({muni_clean})", "Superficie", f"{float(sim['hectares']):.1f} ha"),
        ("Cultivo Base Actual", sim["nombre_comun"], "Régimen Hídrico", regimen_label),
        (
            "Suelo y Clima",
            f"{ctx['tipo_suelo_label']} ({ctx['textura_label']}) · MO {ctx['materia_organica_pct']}% · {int(round(float(ctx['local_elevation_m']))):,} msnm · Lluvia {ctx['annual_simulated_rain_mm']} mm/año (+{sim['temp_increase_c']:.1f} °C)",
            "Prioridades y Preocupaciones",
            f"Agua {w_agua}% · Ganancia {w_prof}% · Suelo/N {w_nit}% | {sim['main_concern_label']}",
        ),
    ]
    for r_i, (k1, v1, k2, v2) in enumerate(meta_rows_2, start=3):
        ws2.cell(row=r_i, column=1, value=k1).font = bold_font
        ws2.cell(row=r_i, column=1).fill = sub_fill
        ws2.merge_cells(start_row=r_i, start_column=1, end_row=r_i, end_column=2)
        ws2.cell(row=r_i, column=3, value=v1).font = body_font
        ws2.merge_cells(start_row=r_i, start_column=3, end_row=r_i, end_column=10)
        ws2.cell(row=r_i, column=11, value=k2).font = bold_font
        ws2.cell(row=r_i, column=11).fill = sub_fill
        ws2.merge_cells(start_row=r_i, start_column=11, end_row=r_i, end_column=12)
        ws2.cell(row=r_i, column=13, value=v2).font = body_font
        ws2.merge_cells(start_row=r_i, start_column=13, end_row=r_i, end_column=19)
        for c_i in range(1, 20):
            mc = ws2.cell(row=r_i, column=c_i)
            mc.border = cell_border
            mc.alignment = Alignment(vertical="center", wrap_text=True)
            if c_i in (1, 2, 11, 12):
                mc.fill = sub_fill
        ws2.row_dimensions[r_i].height = 24

    ws2.row_dimensions[6].height = 10
    ws2["A6"] = "Comparativa del Plan Actual (Línea Base) vs. Top 5 Rotaciones Combinadas a 3 Años"
    ws2["A6"].font = section_font
    ws2.merge_cells("A6:S6")
    ws2.row_dimensions[6].height = 22

    headers_2 = [
        "Posición",
        "Plan de Rotación (3 Años)",
        "Afinidad (%)",
        "Ganancia Neta 3 Años (MXN)",
        "Dinero Extra vs. Actual (MXN)",
        "Agua Total 3 Años (m³)",
        "Agua que Ahorras (m³)",
        "Agua que Ahorras (Litros)",
        "Ahorro Fertilizante N (MXN)",
        "Meses Suelo Protegido (/36)",
        "Ciclos Fijación N",
        "Riesgo Sequía",
        "Riesgo Heladas",
        "Riesgo Plagas",
        "Año 1 (PV / OI)",
        "Año 2 (PV / OI)",
        "Año 3 (PV / OI)",
        "Resumen y Evidencia NASA",
        "ID Técnico Plan",
    ]
    header_row_2 = 7
    for col_i, h in enumerate(headers_2, start=1):
        c = ws2.cell(row=header_row_2, column=col_i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = cell_border
    ws2.row_dimensions[header_row_2].height = 32

    base_plan = next((p for p in sim["plans"] if p["plan_id"] == "plan_actual"), sim["plans"][0])
    base_net = float(base_plan["ingreso_neto_total_mxn"])

    row_cursor = header_row_2
    for p in sim["plans"]:
        row_cursor += 1
        pos_label = f"#{p['rank']} Recomendada" if p.get("rank") == 1 else (f"#{p['rank']}" if p.get("rank") else "Línea Base")
        bal = p.get("balance_nitrogeno_y_cobertura", {})
        y_strs = [f"PV: {y['pv_crop_label']}\nOI: {y['oi_crop_label']}" for y in p.get("years", [])]
        while len(y_strs) < 3:
            y_strs.append("")
        diff_mxn = round(float(p["ingreso_neto_total_mxn"]) - base_net, 2)
        ahorro_m3 = round(float(p.get("ahorro_agua_m3", 0.0)), 1)
        summary_txt = str(p.get("nasa_evidence_summary", ""))

        vals = [
            pos_label,
            p["plan_name"],
            round(float(p["suitability_score"]), 1),
            round(float(p["ingreso_neto_total_mxn"]), 2),
            diff_mxn,
            round(float(p.get("consumo_agua_total_3a_m3", 0.0)), 1),
            ahorro_m3,
            int(round(float(p.get("ahorro_agua_litros", 0)))),
            round(float(p.get("ahorro_fertilizante_n_total_mxn", 0.0)), 2),
            int(bal.get("meses_suelo_protegido_3a", 0)),
            int(bal.get("ciclos_fijacion_nitrogeno_3a", 0)),
            p["semaforo_sequia"],
            p["semaforo_heladas"],
            p["semaforo_plagas"],
            y_strs[0],
            y_strs[1],
            y_strs[2],
            summary_txt,
            p["plan_id"],
        ]
        is_best = p.get("rank") == 1
        for col_i, val in enumerate(vals, start=1):
            c = ws2.cell(row=row_cursor, column=col_i, value=val)
            c.font = bold_font if (is_best or col_i in (1, 2)) else body_font
            c.border = cell_border
            c.alignment = Alignment(
                vertical="center",
                wrap_text=col_i in (2, 15, 16, 17, 18),
                horizontal="center" if col_i in (1, 3, 10, 11, 12, 13, 14) else "left",
            )
            if is_best:
                c.fill = best_fill
            elif p["plan_id"] != "plan_actual" and (row_cursor % 2 == 0):
                c.fill = zebra_fill

            if col_i == 3:
                c.number_format = '0.0"%"'
            elif col_i in (4, 9):
                c.number_format = "$#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i == 5:
                c.number_format = "+$#,##0;-$#,##0;$0"
                c.alignment = Alignment(horizontal="right", vertical="center")
                c.font = pos_font if diff_mxn > 0 else (neg_font if diff_mxn < 0 else body_font)
            elif col_i == 6:
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i in (7, 8):
                c.number_format = "+#,##0;-#,##0;0"
                c.alignment = Alignment(horizontal="right", vertical="center")
                c.font = pos_font if ahorro_m3 > 0 else (neg_font if ahorro_m3 < 0 else body_font)
            elif col_i in (12, 13, 14) and val in light_fills:
                c.fill = light_fills[val]
                c.font = light_fonts[val]
            elif col_i == 19:
                c.font = muted_font

        ws2.row_dimensions[row_cursor].height = _estimate_wrapped_row_height(
            [(y_strs[0], 36), (y_strs[1], 36), (y_strs[2], 36), (summary_txt, 64)],
            min_h=44.0,
        )

    ws2.auto_filter.ref = f"A{header_row_2}:S{row_cursor}"
    ws2.freeze_panes = f"A{header_row_2 + 1}"
    widths_2 = [18, 36, 13, 21, 22, 18, 18, 19, 20, 17, 15, 13, 13, 13, 36, 36, 36, 64, 24]
    for col_i, w in enumerate(widths_2, start=1):
        ws2.column_dimensions[get_column_letter(col_i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@app.post("/api/export-excel")
def api_export_excel(req: SimulateRequest) -> StreamingResponse:
    try:
        effective_crop = req.current_crop or req.familia_cultivo or "Maiz_Grano"
        concerns_arg = req.selected_problems if req.selected_problems else req.main_concern
        sim = simulate_scenarios(
            location_id=req.location_id,
            hectares=req.hectares,
            weight_water=req.weight_water,
            weight_profit=req.weight_profit,
            weight_nitrogen=req.weight_nitrogen,
            rain_reduction_pct=req.rain_reduction_pct,
            temp_increase_c=req.temp_increase_c,
            irrigation_mode=req.irrigation_mode,
            market_goal=req.market_goal,
            current_crop=effective_crop,
            custom_crop_name=req.custom_crop_name,
            custom_crop_water_tier=req.custom_crop_water_tier,
            soil_override=req.soil_override,
            fertilizer_type=req.fertilizer_type,
            tillage_mode=req.tillage_mode,
            main_concern=concerns_arg,
        )
        rows_168 = simulate_all_168_crops(
            location_id=req.location_id,
            hectares=req.hectares,
            weight_water=req.weight_water,
            weight_profit=req.weight_profit,
            weight_nitrogen=req.weight_nitrogen,
            rain_reduction_pct=req.rain_reduction_pct,
            temp_increase_c=req.temp_increase_c,
            irrigation_mode=req.irrigation_mode,
            market_goal=req.market_goal,
            current_crop=effective_crop,
            custom_crop_name=req.custom_crop_name,
            custom_crop_water_tier=req.custom_crop_water_tier,
            soil_override=req.soil_override,
            fertilizer_type=req.fertilizer_type,
            tillage_mode=req.tillage_mode,
            main_concern=concerns_arg,
        )
        xlsx_bytes = _build_excel_workbook(sim, rows_168)
        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="Kultiva_Simulacion_168_Cultivos_Coahuila.xlsx"',
                "Cache-Control": "no-store",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/sw.js")
@app.get("/static/sw.js")
def service_worker() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache",
        },
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

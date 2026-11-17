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


def _build_excel_workbook(sim: dict[str, Any], rows_168: list[dict[str, Any]]) -> bytes:
    wb = Workbook()

    header_fill = PatternFill(start_color="0F5132", end_color="0F5132", fill_type="solid")
    sub_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    best_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    light_fills = {
        "VERDE": PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
        "AMARILLO": PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
        "ROJO": PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
    }
    light_fonts = {
        "VERDE": Font(bold=True, color="166534"),
        "AMARILLO": Font(bold=True, color="92400E"),
        "ROJO": Font(bold=True, color="991B1B"),
    }

    title_font = Font(name="Calibri", size=14, bold=True, color="0F5132")
    section_font = Font(name="Calibri", size=11, bold=True, color="0F5132")
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="Calibri", size=10, color="0F172A")
    bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
    thin_side = Side(style="thin", color="CBD5E1")
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    # =========================================================================
    # PESTAÑA 1: Top_5_Recomendaciones
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Top_5_Recomendaciones"
    ws1["A1"] = "Kultiva · Reporte Satelital NASA y Top 5 Rotaciones Recomendadas (Coahuila)"
    ws1["A1"].font = title_font
    ws1.merge_cells("A1:I1")

    ctx = sim["parcel_context"]
    meta_rows = [
        ("Parcela / Estación", f"{sim['zona_label']} ({sim['municipio']})", "Superficie (ha)", sim["hectares"]),
        ("Cultivo Base Solicitado", sim["requested_crop"], "Variedad Oficial Resuelta", sim["nombre_comun"]),
        ("Familia / Categoría SIAP", f"{sim['familia_cultivo']} · {sim['categoria_siap']}", "Fuente Oficial", sim["fuente_oficial"]),
        ("Régimen Hídrico", sim["irrigation_mode"].capitalize(), "Destino Productivo", sim["market_goal"].capitalize()),
        ("Fertilización / Labranza", f"{sim['fertilizer_label']} · {sim['tillage_label']}", "Preocupaciones", sim["main_concern_label"]),
        (
            "Suelo y Altitud",
            f"{ctx['tipo_suelo_label']} ({ctx['textura_label']}) · MO {ctx['materia_organica_pct']}% · {ctx['local_elevation_m']} msnm · Pend. {ctx['pendiente_pct']}%",
            "Clima Simulado",
            f"Lluvia {ctx['annual_simulated_rain_mm']} mm/año (hist. {ctx['annual_historical_rain_mm']} mm) · +{sim['temp_increase_c']:.1f} °C",
        ),
    ]
    row_idx = 3
    for k1, v1, k2, v2 in meta_rows:
        ws1.cell(row=row_idx, column=1, value=k1).font = bold_font
        ws1.cell(row=row_idx, column=1).fill = sub_fill
        ws1.cell(row=row_idx, column=2, value=v1).font = body_font
        ws1.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=4)
        ws1.cell(row=row_idx, column=5, value=k2).font = bold_font
        ws1.cell(row=row_idx, column=5).fill = sub_fill
        ws1.cell(row=row_idx, column=6, value=v2).font = body_font
        ws1.merge_cells(start_row=row_idx, start_column=6, end_row=row_idx, end_column=9)
        for c in range(1, 10):
            ws1.cell(row=row_idx, column=c).border = cell_border
            ws1.cell(row=row_idx, column=c).alignment = Alignment(vertical="center", wrap_text=True)
        ws1.row_dimensions[row_idx].height = 22
        row_idx += 1

    row_idx += 1
    ws1.cell(row=row_idx, column=1, value="Comparativa Plan Actual (Línea Base) vs. Top 5 Recomendaciones a 3 Años").font = section_font
    ws1.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=10)
    row_idx += 1

    headers_1 = [
        "Posición",
        "ID Plan",
        "Nombre del Plan",
        "Afinidad (%)",
        "Utilidad Neta 3A (MXN)",
        "Diferencia vs Actual (MXN)",
        "Consumo Agua 3A (m³)",
        "Ahorro Agua 3A (m³)",
        "Ahorro Agua (L)",
        "Ahorro Fertilizante N (MXN)",
        "Suelo Cubierto (/36 m)",
        "Ciclos Fijación N",
        "Sequía",
        "Heladas",
        "Plagas",
        "Año 1 (PV / OI)",
        "Año 2 (PV / OI)",
        "Año 3 (PV / OI)",
        "Estrategia y Evidencia NASA",
    ]
    header_row_1 = row_idx
    for col_i, h in enumerate(headers_1, start=1):
        cell = ws1.cell(row=header_row_1, column=col_i, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = cell_border
    ws1.row_dimensions[header_row_1].height = 28

    base_plan = next((p for p in sim["plans"] if p["plan_id"] == "plan_actual"), sim["plans"][0])
    base_net = float(base_plan["ingreso_neto_total_mxn"])

    for p in sim["plans"]:
        row_idx += 1
        pos_label = f"#{p['rank']} Recomendada" if p.get("rank") == 1 else (f"#{p['rank']}" if p.get("rank") else "Línea Base")
        bal = p.get("balance_nitrogeno_y_cobertura", {})
        y_strs = [f"PV: {y['pv_crop_label']} | OI: {y['oi_crop_label']}" for y in p.get("years", [])]
        while len(y_strs) < 3:
            y_strs.append("")

        vals = [
            pos_label,
            p["plan_id"],
            p["plan_name"],
            round(float(p["suitability_score"]), 2),
            round(float(p["ingreso_neto_total_mxn"]), 2),
            round(float(p["ingreso_neto_total_mxn"]) - base_net, 2),
            round(float(p.get("consumo_agua_total_3a_m3", 0.0)), 1),
            round(float(p.get("ahorro_agua_m3", 0.0)), 1),
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
            p.get("nasa_evidence_summary", ""),
        ]
        is_best = p.get("rank") == 1
        for col_i, val in enumerate(vals, start=1):
            c = ws1.cell(row=row_idx, column=col_i, value=val)
            c.font = bold_font if (is_best or col_i in (1, 3)) else body_font
            c.border = cell_border
            c.alignment = Alignment(vertical="center", wrap_text=True, horizontal="center" if col_i in (1, 4, 11, 12, 13, 14, 15) else "left")
            if is_best:
                c.fill = best_fill
            elif p["plan_id"] != "plan_actual" and (row_idx % 2 == 0):
                c.fill = zebra_fill

            if col_i == 4:
                c.number_format = "0.0"
            elif col_i in (5, 6, 10):
                c.number_format = "$#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i in (7, 8, 9):
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i in (13, 14, 15) and val in light_fills:
                c.fill = light_fills[val]
                c.font = light_fonts[val]
        ws1.row_dimensions[row_idx].height = 46

    ws1.auto_filter.ref = f"A{header_row_1}:S{row_idx}"
    ws1.freeze_panes = f"A{header_row_1 + 1}"
    widths_1 = [18, 22, 34, 13, 20, 22, 18, 18, 18, 20, 16, 14, 12, 12, 12, 34, 34, 34, 58]
    for col_i, w in enumerate(widths_1, start=1):
        ws1.column_dimensions[get_column_letter(col_i)].width = w

    # =========================================================================
    # PESTAÑA 2: Simulacion_168_Cultivos
    # =========================================================================
    ws2 = wb.create_sheet(title="Simulacion_168_Cultivos")
    headers_2 = [
        "Ranking",
        "ID Cultivo",
        "Nombre Común Oficial",
        "Familia SIAP",
        "Categoría SIAP",
        "Modo en Kultiva",
        "Clasificación Oficial",
        "Afinidad (%)",
        "Puntaje Agua",
        "Puntaje Rentabilidad",
        "Puntaje Suelo y N",
        "Consumo Agua Base (mm)",
        "Agua Consumida 3A (m³)",
        "Ahorro Agua vs Actual (m³)",
        "Ahorro Agua vs Actual (L)",
        "Utilidad Neta 3A (MXN)",
        "Diferencia Dinero vs Actual (MXN)",
        "Ahorro Fertilizante 3A (MXN)",
        "Meses Suelo Protegido (/36)",
        "Semáforo Sequía",
        "Semáforo Heladas",
        "Semáforo Plagas",
        "Municipios Coahuila",
        "Fuente Oficial",
        "Resumen de Escenario (Qué pasaría en tu parcela)",
    ]
    for col_i, h in enumerate(headers_2, start=1):
        c = ws2.cell(row=1, column=col_i, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = cell_border
    ws2.row_dimensions[1].height = 30

    for r_idx, item in enumerate(rows_168, start=2):
        row_vals = [
            int(item["ranking"]),
            item["cultivo"],
            item["nombre_comun"],
            item["familia_cultivo"],
            item["categoria_siap"],
            item["modo_en_kultiva"],
            item["clasificacion_oficial"],
            round(float(item["suitability_score"]), 2),
            round(float(item["water_score"]), 1),
            round(float(item["profit_score"]), 1),
            round(float(item["nitrogen_soil_score"]), 1),
            round(float(item["consumo_agua_base_mm"]), 1),
            round(float(item["agua_consumida_3a_m3"]), 1),
            round(float(item["ahorro_agua_vs_actual_m3"]), 1),
            int(item["ahorro_agua_vs_actual_litros"]),
            round(float(item["utilidad_neta_3a_mxn"]), 2),
            round(float(item["diferencia_dinero_vs_actual_mxn"]), 2),
            round(float(item["ahorro_fertilizante_3a_mxn"]), 2),
            int(item["meses_suelo_protegido_36"]),
            item["semaforo_sequia"],
            item["semaforo_heladas"],
            item["semaforo_plagas"],
            item["municipios_coahuila"],
            item["fuente_oficial"],
            item["resumen_escenario"],
        ]
        is_top5 = item["ranking"] <= 5
        for col_i, val in enumerate(row_vals, start=1):
            c = ws2.cell(row=r_idx, column=col_i, value=val)
            c.font = bold_font if (is_top5 and col_i in (1, 3, 8)) else body_font
            c.border = cell_border
            c.alignment = Alignment(
                vertical="center",
                wrap_text=col_i in (3, 7, 23, 24, 25),
                horizontal="center" if col_i in (1, 19, 20, 21, 22) else "left",
            )
            if is_top5:
                c.fill = sub_fill
            elif r_idx % 2 == 1:
                c.fill = zebra_fill

            if col_i in (8, 9, 10, 11):
                c.number_format = "0.0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i in (12, 13, 14, 15):
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i in (16, 17, 18):
                c.number_format = "$#,##0"
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_i in (20, 21, 22) and val in light_fills:
                c.fill = light_fills[val]
                c.font = light_fonts[val]
        ws2.row_dimensions[r_idx].height = 28

    ws2.auto_filter.ref = f"A1:Y{len(rows_168) + 1}"
    ws2.freeze_panes = "A2"
    widths_2 = [10, 34, 46, 24, 24, 26, 32, 13, 13, 16, 16, 18, 19, 20, 20, 20, 22, 20, 18, 14, 14, 14, 42, 42, 62]
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

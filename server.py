from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agroshift_engine import simulate_scenarios


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
STATIC_DIR = BASE_DIR / "static"
MONTHLY_CSV_PATH = DATA_DIR / "agroshift_parcelas_monthly.csv"

app = FastAPI(title="Cultiva API", version="2.1")


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
    current_crop: str = Field(default="Maiz_Grano")
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
    return {
        "suelos": _read_json("suelos_coahuila_clean.json"),
        "cultivos": _read_json("cultivos_coahuila_clean.json"),
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
            current_crop=req.current_crop,
            custom_crop_name=req.custom_crop_name,
            custom_crop_water_tier=req.custom_crop_water_tier,
            soil_override=req.soil_override,
            fertilizer_type=req.fertilizer_type,
            tillage_mode=req.tillage_mode,
            main_concern=req.selected_problems if req.selected_problems else req.main_concern,
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

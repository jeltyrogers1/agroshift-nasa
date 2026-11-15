import json
from pathlib import Path
import pandas as pd


DAILY_NASA_PATH = Path("data/processed/nasa_power_coahuila_daily.csv")
MONTHLY_NASA_PATH = Path("data/processed/nasa_power_coahuila_monthly.csv")
MONTHLY_MODIS_PATH = Path("data/processed/modis_ndvi_coahuila_monthly.csv")
SUELOS_PATH = Path("data/processed/suelos_coahuila_clean.csv")

MASTER_MONTHLY_PATH = Path("data/processed/agroshift_parcelas_monthly.csv")
CLIMATOLOGY_JSON_PATH = Path("data/processed/agroshift_climatology_12m.json")

MONTH_NAMES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

SOIL_METADATA_COLS = [
    "location_id",
    "zona_label",
    "municipio",
    "latitud",
    "longitud",
    "local_elevation_m",
    "tipo_suelo_label",
    "textura_label",
    "materia_organica_pct",
    "pendiente_pct",
    "water_retention_score",
    "erosion_risk_score",
    "needs_nitrogen_fixation",
    "needs_erosion_cover",
    "high_drought_vulnerability",
    "problema_principal",
]


def update_nasa_power_with_pest_risk() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add pest_risk to daily NASA POWER and recompute monthly summary with pest_risk_days."""
    daily = pd.read_csv(DAILY_NASA_PATH)

    daily["pest_risk"] = (
        (daily["T2M"] >= 20.0) & (daily["T2M"] <= 32.0) & (daily["RH2M"] >= 65.0)
    ).astype("int64")
    daily.to_csv(DAILY_NASA_PATH, index=False)

    monthly = (
        daily.groupby(["location_id", "YEAR", "month", "season"], as_index=False, sort=False)
        .agg(
            t2m_mean=("T2M", "mean"),
            t2m_max_mean=("T2M_MAX", "mean"),
            t2m_min_mean=("T2M_MIN", "mean"),
            soil_moisture_avg_mean=("soil_moisture_avg", "mean"),
            allsky_sfc_sw_dwn_mean=("ALLSKY_SFC_SW_DWN", "mean"),
            ws2m_mean=("WS2M", "mean"),
            prectotcorr_sum=("PRECTOTCORR", "sum"),
            gdd_base10_sum=("gdd_base10", "sum"),
            frost_risk_days=("frost_risk", "sum"),
            pest_risk_days=("pest_risk", "sum"),
        )
    )
    monthly.to_csv(MONTHLY_NASA_PATH, index=False)
    return daily, monthly


def build_monthly_master(
    nasa_monthly: pd.DataFrame,
    modis_monthly: pd.DataFrame,
    suelos: pd.DataFrame,
) -> pd.DataFrame:
    """Integrate monthly NASA POWER, MODIS NDVI, and soil master tables."""
    nasa_renamed = nasa_monthly.rename(columns={"YEAR": "year"}).copy()

    merged = nasa_renamed.merge(
        modis_monthly,
        on=["location_id", "year", "month"],
        how="inner",
        validate="one_to_one",
    )
    merged = merged.merge(
        suelos,
        on="location_id",
        how="left",
        validate="many_to_one",
    )

    assert merged["zona_label"].isna().sum() == 0, "Faltan cruces con suelos_coahuila_clean."

    merged["bare_soil_or_stress_alert"] = (
        (merged["ndvi_mean"] < 0.25) | (merged["ndvi_anomaly_mean"] < -0.05)
    ).astype("int64")

    merged = merged.sort_values(["location_id", "year", "month"]).reset_index(drop=True)
    merged.to_csv(MASTER_MONTHLY_PATH, index=False)
    return merged


def build_climatology_json(master: pd.DataFrame, suelos: pd.DataFrame) -> dict:
    """Aggregate 12-month historical climatology (2016-2026) per plot and export JSON."""
    clim = (
        master.groupby(["location_id", "month", "season"], as_index=False)
        .agg(
            years_sampled=("year", "count"),
            prectotcorr_mm_mean=("prectotcorr_sum", "mean"),
            t2m_c_mean=("t2m_mean", "mean"),
            t2m_min_c_mean=("t2m_min_mean", "mean"),
            t2m_max_c_mean=("t2m_max_mean", "mean"),
            soil_moisture_avg_mean=("soil_moisture_avg_mean", "mean"),
            ndvi_mean=("ndvi_mean", "mean"),
            frost_risk_days_mean=("frost_risk_days", "mean"),
            pest_risk_days_mean=("pest_risk_days", "mean"),
            bare_soil_or_stress_freq=("bare_soil_or_stress_alert", "mean"),
        )
        .sort_values(["location_id", "month"])
        .reset_index(drop=True)
    )

    period_start = f"{int(master['year'].min())}-{int(master.loc[master['year'] == master['year'].min(), 'month'].min()):02d}"
    period_end = f"{int(master['year'].max())}-{int(master.loc[master['year'] == master['year'].max(), 'month'].max()):02d}"

    locations_payload = {}
    for _, soil_row in suelos.iterrows():
        loc_id = soil_row["location_id"]
        loc_clim = clim[clim["location_id"] == loc_id].sort_values("month")

        months_list = []
        for _, m_row in loc_clim.iterrows():
            m_num = int(m_row["month"])
            months_list.append(
                {
                    "month": m_num,
                    "month_name": MONTH_NAMES_ES[m_num],
                    "season": m_row["season"],
                    "years_sampled": int(m_row["years_sampled"]),
                    "prectotcorr_mm_mean": round(float(m_row["prectotcorr_mm_mean"]), 4),
                    "t2m_c_mean": round(float(m_row["t2m_c_mean"]), 4),
                    "t2m_min_c_mean": round(float(m_row["t2m_min_c_mean"]), 4),
                    "t2m_max_c_mean": round(float(m_row["t2m_max_c_mean"]), 4),
                    "soil_moisture_avg_mean": round(float(m_row["soil_moisture_avg_mean"]), 4),
                    "ndvi_mean": round(float(m_row["ndvi_mean"]), 4),
                    "frost_risk_days_mean": round(float(m_row["frost_risk_days_mean"]), 4),
                    "pest_risk_days_mean": round(float(m_row["pest_risk_days_mean"]), 4),
                    "bare_soil_or_stress_freq": round(float(m_row["bare_soil_or_stress_freq"]), 4),
                }
            )

        soil_info = {}
        for col in SOIL_METADATA_COLS:
            if col == "location_id":
                continue
            val = soil_row[col]
            soil_info[col] = val.item() if hasattr(val, "item") else val

        locations_payload[loc_id] = {
            "location_id": loc_id,
            "soil": soil_info,
            "months": months_list,
        }

    payload = {
        "metadata": {
            "period_start": period_start,
            "period_end": period_end,
            "total_monthly_records": int(len(master)),
            "locations_count": int(len(locations_payload)),
            "pest_risk_rule": "T2M >= 20.0 AND T2M <= 32.0 AND RH2M >= 65.0",
            "bare_soil_or_stress_rule": "ndvi_mean < 0.25 OR ndvi_anomaly_mean < -0.05",
        },
        "locations": locations_payload,
    }

    with CLIMATOLOGY_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def print_console_report(
    daily: pd.DataFrame,
    nasa_monthly: pd.DataFrame,
    master: pd.DataFrame,
    climatology: dict,
) -> None:
    """Print integration metrics and per-plot stress, frost, and pest peak months."""
    print("=== 1. ACTUALIZACIÓN NASA POWER (RIESGO DE PLAGAS) ===")
    print(f"Registros diarios ({DAILY_NASA_PATH}):  {len(daily)}")
    print(f"Registros mensuales ({MONTHLY_NASA_PATH}): {len(nasa_monthly)}")
    pest_summary = daily.groupby("location_id")["pest_risk"].agg(dias_plaga="sum", tasa_diaria="mean")
    print(pest_summary.to_string())

    print("\n=== 2. TABLA MAESTRA MENSUAL INTEGRADA ===")
    print(f"Archivo generado: {MASTER_MONTHLY_PATH}")
    print(f"Total filas integradas: {len(master)} | Columnas: {len(master.columns)}")
    print(
        f"Rango temporal integrado: {climatology['metadata']['period_start']} "
        f"a {climatology['metadata']['period_end']}"
    )
    print(f"Total alertas suelo desnudo/estrés: {int(master['bare_soil_or_stress_alert'].sum())}")

    print("\n=== 3. PERFIL CLIMATOLÓGICO 12M POR PARCELA (2016-2026) ===")
    for loc_id, loc_data in climatology["locations"].items():
        months_df = pd.DataFrame(loc_data["months"])
        zona = loc_data["soil"]["zona_label"]

        top_stress = months_df.sort_values(
            ["bare_soil_or_stress_freq", "soil_moisture_avg_mean"], ascending=[False, True]
        ).head(3)
        top_dry = months_df.sort_values("soil_moisture_avg_mean", ascending=True).head(3)
        top_frost = months_df[months_df["frost_risk_days_mean"] > 0].sort_values(
            "frost_risk_days_mean", ascending=False
        ).head(3)
        top_pest = months_df[months_df["pest_risk_days_mean"] > 0].sort_values(
            "pest_risk_days_mean", ascending=False
        ).head(3)

        stress_str = ", ".join(
            f"{r['month_name']} ({r['bare_soil_or_stress_freq']*100:.1f}% alerta, hum={r['soil_moisture_avg_mean']:.3f})"
            for _, r in top_stress.iterrows()
        )
        dry_str = ", ".join(
            f"{r['month_name']} (hum={r['soil_moisture_avg_mean']:.3f}, lluvia={r['prectotcorr_mm_mean']:.1f} mm)"
            for _, r in top_dry.iterrows()
        )
        frost_str = ", ".join(
            f"{r['month_name']} ({r['frost_risk_days_mean']:.2f} días/mes)"
            for _, r in top_frost.iterrows()
        )
        pest_str = ", ".join(
            f"{r['month_name']} ({r['pest_risk_days_mean']:.2f} días/mes)"
            for _, r in top_pest.iterrows()
        )

        print(f"\n[{loc_id}] - {zona}")
        print(f"  * Mayor alerta suelo desnudo/estrés NDVI: {stress_str}")
        print(f"  * Menor humedad de suelo (estrés hídrico): {dry_str}")
        print(f"  * Mayor riesgo de heladas:                {frost_str if frost_str else 'Sin heladas'}")
        print(f"  * Mayor riesgo de plagas:                 {pest_str if pest_str else 'Sin riesgo'}")


def main() -> None:
    daily, nasa_monthly = update_nasa_power_with_pest_risk()
    modis_monthly = pd.read_csv(MONTHLY_MODIS_PATH)
    suelos = pd.read_csv(SUELOS_PATH)

    master = build_monthly_master(nasa_monthly, modis_monthly, suelos)
    climatology = build_climatology_json(master, suelos)
    print_console_report(daily, nasa_monthly, master, climatology)


if __name__ == "__main__":
    main()

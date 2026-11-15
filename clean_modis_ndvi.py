from pathlib import Path
import numpy as np
import pandas as pd


INPUT_PATH = Path("coahuila-ndvi-MOD13Q1-061-results.csv")
OUTPUT_CLEAN_PATH = Path("data/processed/modis_ndvi_coahuila_clean.csv")
OUTPUT_MONTHLY_PATH = Path("data/processed/modis_ndvi_coahuila_monthly.csv")

LOCATION_ID_MAP = {
    "LaNarro": "UAAAN_La_Narro",
    "LosLirios": "Los_Lirios_Arteaga",
    "GeneralCepeda": "General_Cepeda",
}

SEASON_MAP = {
    12: "Invierno",
    1: "Invierno",
    2: "Invierno",
    3: "Primavera",
    4: "Primavera",
    5: "Primavera",
    6: "Verano",
    7: "Verano",
    8: "Verano",
    9: "Otoño",
    10: "Otoño",
    11: "Otoño",
}


def classify_vegetation(ndvi: float) -> str:
    if pd.isna(ndvi):
        return np.nan
    if ndvi < 0.25:
        return "Suelo_Desnudo_o_Rastrojo"
    if ndvi < 0.40:
        return "Vegetacion_Escasa_o_Estres"
    if ndvi < 0.55:
        return "Cobertura_Moderada"
    return "Vigor_Vegetal_Alto"


def interpolate_group_time(group: pd.DataFrame) -> pd.Series:
    series = pd.Series(group["ndvi_clean"].values, index=group["date_dt"])
    return pd.Series(
        series.interpolate(method="time", limit=2, limit_area="inside").values,
        index=group.index,
    )


def main() -> None:
    df = pd.read_csv(INPUT_PATH, encoding="utf-8")

    # 1. Carga y estandarización de llaves
    df["location_id"] = df["ID"].astype(str).str.strip().map(LOCATION_ID_MAP)
    assert df["location_id"].isna().sum() == 0, "Existen IDs no mapeados a location_id."

    df["date_dt"] = pd.to_datetime(df["Date"])
    df["date"] = df["date_dt"].dt.strftime("%Y-%m-%d")
    df["year"] = df["date_dt"].dt.year.astype("int64")
    df["month"] = df["date_dt"].dt.month.astype("int64")
    df["season"] = df["month"].map(SEASON_MAP)

    df = df.rename(
        columns={
            "MOD13Q1_061__250m_16_days_NDVI": "ndvi_raw",
            "MOD13Q1_061__250m_16_days_VI_Quality_MODLAND_Description": "qa_status",
        }
    )

    df = df.sort_values(["location_id", "date_dt"]).reset_index(drop=True)

    # 2. Filtrado de calidad satelital (QA) e interpolación
    mixed_clouds_col = "MOD13Q1_061__250m_16_days_VI_Quality_Mixed_Clouds_Description"
    contaminated_mask = (
        (df["qa_status"] == "Pixel produced, but most probably cloudy")
        | (df[mixed_clouds_col] == "Yes")
        | (df["ndvi_raw"] < -0.2)
        | (df["ndvi_raw"] > 1.0)
    )
    df["is_cloud_contaminated"] = contaminated_mask.astype("int64")

    df["ndvi_clean"] = df["ndvi_raw"].where(~contaminated_mask, np.nan)
    df["ndvi_clean"] = df.groupby("location_id", group_keys=False).apply(
        interpolate_group_time, include_groups=False
    )

    # 3. Ingeniería de variables de vigor vegetal
    df["ndvi_rolling_3"] = (
        df.groupby("location_id")["ndvi_clean"]
        .transform(lambda s: s.rolling(window=3, min_periods=1).mean())
    )
    df["ndvi_monthly_climatology"] = (
        df.groupby(["location_id", "month"])["ndvi_clean"].transform("mean")
    )
    df["ndvi_anomaly"] = df["ndvi_clean"] - df["ndvi_monthly_climatology"]
    df["vegetation_cover_state"] = df["ndvi_clean"].apply(classify_vegetation)

    # 4. Selección de columnas y entregables
    selected_cols = [
        "location_id",
        "date",
        "year",
        "month",
        "season",
        "Latitude",
        "Longitude",
        "ndvi_raw",
        "ndvi_clean",
        "ndvi_rolling_3",
        "ndvi_anomaly",
        "vegetation_cover_state",
        "qa_status",
        "is_cloud_contaminated",
    ]
    df_clean = df[selected_cols].copy()

    OUTPUT_CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(OUTPUT_CLEAN_PATH, index=False, encoding="utf-8")

    df_monthly = (
        df_clean.groupby(["location_id", "year", "month"], as_index=False)
        .agg(
            ndvi_mean=("ndvi_clean", "mean"),
            ndvi_min=("ndvi_clean", "min"),
            ndvi_max=("ndvi_clean", "max"),
            ndvi_anomaly_mean=("ndvi_anomaly", "mean"),
        )
        .sort_values(["location_id", "year", "month"])
        .reset_index(drop=True)
    )
    df_monthly.to_csv(OUTPUT_MONTHLY_PATH, index=False, encoding="utf-8")

    # Reporte en consola
    print("=== REPORTE DE LIMPIEZA MODIS NDVI (COAHUILA) ===")
    summary_rows = []
    for loc, grp in df_clean.groupby("location_id"):
        total = len(grp)
        flagged = int(grp["is_cloud_contaminated"].sum())
        interpolated = int(
            (grp["is_cloud_contaminated"] == 1).sum() - grp["ndvi_clean"].isna().sum()
        )
        summary_rows.append(
            {
                "location_id": loc,
                "total_registros": total,
                "pixeles_nublados_filtrados": flagged,
                "pixeles_interpolados": interpolated,
                "nulos_restantes": int(grp["ndvi_clean"].isna().sum()),
                "ndvi_min": round(float(grp["ndvi_clean"].min()), 4),
                "ndvi_mean": round(float(grp["ndvi_clean"].mean()), 4),
                "ndvi_max": round(float(grp["ndvi_clean"].max()), 4),
            }
        )
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print(f"\nTotal registros limpios (16 días): {len(df_clean)}")
    print(f"Total registros mensuales:         {len(df_monthly)}")


if __name__ == "__main__":
    main()

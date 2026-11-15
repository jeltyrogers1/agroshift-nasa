"""Clean and standardize NASA POWER daily weather data for Los Lirios, Arteaga."""

from pathlib import Path
import numpy as np
import pandas as pd

INPUT_PATH = Path("nasa_power_los_lirios.csv")
REFERENCE_CLEAN_PATH = Path("data/processed/nasa_power_la_narro_clean.csv")
REFERENCE_MONTHLY_PATH = Path("data/processed/nasa_power_la_narro_monthly.csv")
OUTPUT_CLEAN_PATH = Path("data/processed/nasa_power_los_lirios_clean.csv")
OUTPUT_MONTHLY_PATH = Path("data/processed/nasa_power_los_lirios_monthly.csv")

LOCATION_ID = "Los_Lirios_Arteaga"
LATITUDE = 25.3929
LONGITUDE = -100.5929
ELEVATION_M = 1626.96

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


def main() -> None:
    # 1. Load raw CSV skipping 18 metadata lines, replacing -999 / -999.0 with NaN
    df = pd.read_csv(INPUT_PATH, skiprows=18, na_values=[-999, -999.0])
    initial_rows = len(df)

    # 2. Dates & chronological sorting
    date_series = pd.to_datetime(
        df["YEAR"].astype(str) + df["DOY"].astype(str).str.zfill(3),
        format="%Y%j",
    )
    df["date"] = date_series.dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").reset_index(drop=True)
    df["month"] = date_series.loc[df.index].dt.month.astype("int64")
    df["season"] = df["month"].map(SEASON_MAP)

    # 3. Plot identifiers
    df["location_id"] = LOCATION_ID
    df["latitude"] = LATITUDE
    df["longitude"] = LONGITUDE
    df["elevation_m"] = ELEVATION_M

    # 4. Null handling
    weather_soil_cols = [
        "ALLSKY_SFC_SW_DWN",
        "T2M",
        "T2M_MAX",
        "T2M_MIN",
        "RH2M",
        "IMERG_PRECTOT",
        "GWETTOP",
        "GWETROOT",
        "WS2M",
        "PRECTOTCORR",
    ]
    df = df.dropna(subset=weather_soil_cols, how="all").reset_index(drop=True)

    for col in ("ALLSKY_SFC_SW_DWN", "IMERG_PRECTOT"):
        df[col] = df[col].interpolate(
            method="linear",
            limit=3,
            limit_area="inside",
        )

    # 5. Agronomic feature engineering
    df["temp_range"] = df["T2M_MAX"] - df["T2M_MIN"]
    df["gdd_base10"] = np.maximum(0.0, ((df["T2M_MAX"] + df["T2M_MIN"]) / 2.0) - 10.0)
    df["soil_moisture_avg"] = (df["GWETTOP"] + df["GWETROOT"]) / 2.0
    df["frost_risk"] = (df["T2M_MIN"] <= 2.0).astype("int64")

    # 6. Align schema & column order with La Narro clean dataset
    ref_clean = pd.read_csv(REFERENCE_CLEAN_PATH, nrows=5)
    df = df[ref_clean.columns.tolist()]

    OUTPUT_CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CLEAN_PATH, index=False)

    # 7. Monthly/seasonal summary
    monthly = (
        df.groupby(["location_id", "YEAR", "month", "season"], as_index=False, sort=False)
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
        )
    )
    ref_monthly = pd.read_csv(REFERENCE_MONTHLY_PATH, nrows=5)
    monthly = monthly[ref_monthly.columns.tolist()]
    monthly.to_csv(OUTPUT_MONTHLY_PATH, index=False)

    # 8. Console verification report
    ref_clean_full = pd.read_csv(REFERENCE_CLEAN_PATH)
    cols_match = list(df.columns) == list(ref_clean_full.columns)
    dtypes_match = df.dtypes.equals(ref_clean_full.dtypes)

    print("=== REPORTE DE LIMPIEZA: LOS LIRIOS, ARTEAGA ===")
    print(f"Filas iniciales: {initial_rows}")
    print(f"Filas finales:   {len(df)} (eliminadas: {initial_rows - len(df)})")
    print(f"Rango de fechas: {df['date'].min()} a {df['date'].max()}")
    print(f"Columnas 100% idénticas a La Narro: {cols_match}")
    print(f"Tipos de datos (dtypes) 100% idénticos a La Narro: {dtypes_match}")
    if not dtypes_match:
        for col in df.columns:
            if df[col].dtype != ref_clean_full[col].dtype:
                print(f"  Diferencia en {col}: {df[col].dtype} vs {ref_clean_full[col].dtype}")
    print("\nNulos restantes por columna:")
    nulls = df.isna().sum()
    print(nulls[nulls > 0] if (nulls > 0).any() else "Ninguno")
    print(f"\nResumen mensual guardado en: {OUTPUT_MONTHLY_PATH} ({len(monthly)} filas)")


if __name__ == "__main__":
    main()

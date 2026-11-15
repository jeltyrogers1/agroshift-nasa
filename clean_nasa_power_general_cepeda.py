"""Clean and standardize NASA POWER daily weather data for General Cepeda and consolidate Coahuila sites."""

from pathlib import Path
import numpy as np
import pandas as pd

INPUT_PATH = Path("nasa_power_general_cepeda.csv")
LA_NARRO_CLEAN_PATH = Path("data/processed/nasa_power_la_narro_clean.csv")
LOS_LIRIOS_CLEAN_PATH = Path("data/processed/nasa_power_los_lirios_clean.csv")
OUTPUT_CLEAN_PATH = Path("data/processed/nasa_power_general_cepeda_clean.csv")

LA_NARRO_MONTHLY_PATH = Path("data/processed/nasa_power_la_narro_monthly.csv")
LOS_LIRIOS_MONTHLY_PATH = Path("data/processed/nasa_power_los_lirios_monthly.csv")
OUTPUT_MONTHLY_PATH = Path("data/processed/nasa_power_general_cepeda_monthly.csv")

MASTER_DAILY_PATH = Path("data/processed/nasa_power_coahuila_daily.csv")
MASTER_MONTHLY_PATH = Path("data/processed/nasa_power_coahuila_monthly.csv")

LOCATION_ID = "General_Cepeda"
LATITUDE = 25.3736
LONGITUDE = -101.4863
ELEVATION_M = 1611.58

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
    ref_clean = pd.read_csv(LA_NARRO_CLEAN_PATH)
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
    ref_monthly = pd.read_csv(LA_NARRO_MONTHLY_PATH)
    monthly = monthly[ref_monthly.columns.tolist()]
    monthly.to_csv(OUTPUT_MONTHLY_PATH, index=False)

    # 8. Regional consolidation (3 sites)
    df_narro = ref_clean
    df_lirios = pd.read_csv(LOS_LIRIOS_CLEAN_PATH)
    df_cepeda = pd.read_csv(OUTPUT_CLEAN_PATH)

    cols_identical = (
        list(df_narro.columns) == list(df_lirios.columns) == list(df_cepeda.columns)
    )
    dtypes_identical = (
        df_narro.dtypes.equals(df_lirios.dtypes)
        and df_narro.dtypes.equals(df_cepeda.dtypes)
    )

    master_daily = pd.concat([df_narro, df_lirios, df_cepeda], ignore_index=True)
    master_daily.to_csv(MASTER_DAILY_PATH, index=False)

    m_narro = ref_monthly
    m_lirios = pd.read_csv(LOS_LIRIOS_MONTHLY_PATH)
    m_cepeda = pd.read_csv(OUTPUT_MONTHLY_PATH)
    master_monthly = pd.concat([m_narro, m_lirios, m_cepeda], ignore_index=True)
    master_monthly.to_csv(MASTER_MONTHLY_PATH, index=False)

    # 9. Console report
    print("=== REPORTE DE LIMPIEZA: GENERAL CEPEDA ===")
    print(f"Filas iniciales: {initial_rows}")
    print(f"Filas finales:   {len(df)} (eliminadas: {initial_rows - len(df)})")
    print(f"Rango de fechas: {df['date'].min()} a {df['date'].max()}")
    print("\nNulos restantes por columna (General Cepeda):")
    nulls = df.isna().sum()
    print(nulls[nulls > 0] if (nulls > 0).any() else "Ninguno")

    print("\n=== CONSOLIDACIÓN REGIONAL (3 SITIOS - COAHUILA) ===")
    print(f"Columnas 100% idénticas (La Narro / Los Lirios / General Cepeda): {cols_identical}")
    print(f"Tipos de datos (dtypes) 100% idénticos: {dtypes_identical}")
    print(f"Total registros diarios consolidados ({MASTER_DAILY_PATH}): {len(master_daily)}")
    print(f"Total registros mensuales consolidados ({MASTER_MONTHLY_PATH}): {len(master_monthly)}")


if __name__ == "__main__":
    main()

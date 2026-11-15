from pathlib import Path
import numpy as np
import pandas as pd


INPUT_PATH = Path("nasa_power_la_narro.csv")
OUTPUT_CLEAN_PATH = Path("data/processed/nasa_power_la_narro_clean.csv")
OUTPUT_MONTHLY_PATH = Path("data/processed/nasa_power_la_narro_monthly.csv")

WEATHER_SOIL_COLS = [
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
    # 1. Inspección y Carga
    df = pd.read_csv(
        INPUT_PATH,
        skiprows=18,
        na_values=[-999, -999.0],
    )
    initial_rows = len(df)

    # 2. Limpieza y Estandarización
    # Fechas a partir de YEAR y DOY
    dt = pd.to_datetime(
        df["YEAR"].astype(int).astype(str) + df["DOY"].astype(int).astype(str).str.zfill(3),
        format="%Y%j",
    )
    df["date"] = dt.dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").reset_index(drop=True)
    df["month"] = dt.loc[df.index].dt.month.astype(int)
    df["season"] = df["month"].map(SEASON_MAP)

    # Identificador de parcela
    df["location_id"] = "UAAAN_La_Narro"
    df["latitude"] = 25.3413
    df["longitude"] = -101.0295
    df["elevation_m"] = 1611.58

    # Manejo de nulos: eliminar filas donde todas las variables meteorológicas/suelo son NaN
    df = df.dropna(subset=WEATHER_SOIL_COLS, how="all").reset_index(drop=True)

    # Imputación de huecos cortos (<= 3 días) en variables con rezago reciente;
    # los bloques finales largos se mantienen como NaN explícito.
    for col in ["ALLSKY_SFC_SW_DWN", "IMERG_PRECTOT"]:
        df[col] = df[col].interpolate(method="linear", limit=3, limit_area="inside")

    # 3. Ingeniería de Variables Agronómicas
    df["temp_range"] = df["T2M_MAX"] - df["T2M_MIN"]
    df["gdd_base10"] = (((df["T2M_MAX"] + df["T2M_MIN"]) / 2.0) - 10.0).clip(lower=0.0)
    df["soil_moisture_avg"] = (df["GWETTOP"] + df["GWETROOT"]) / 2.0
    df["frost_risk"] = (df["T2M_MIN"] <= 2.0).astype(int)

    # 4. Entregables
    OUTPUT_CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CLEAN_PATH, index=False)

    monthly_df = (
        df.groupby(["location_id", "YEAR", "month", "season"], as_index=False)
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
        .sort_values(["YEAR", "month"])
        .reset_index(drop=True)
    )
    monthly_df.to_csv(OUTPUT_MONTHLY_PATH, index=False)

    # Reporte en consola
    final_rows = len(df)
    print("=== REPORTE DE DEPURACIÓN NASA POWER (UAAAN La Narro) ===")
    print(f"Filas iniciales: {initial_rows}")
    print(f"Filas finales:   {final_rows} (eliminadas: {initial_rows - final_rows})")
    print(f"Rango de fechas: {df['date'].min()} -> {df['date'].max()}")
    print(f"Resumen mensual: {len(monthly_df)} registros guardados en {OUTPUT_MONTHLY_PATH}")
    print("\nNulos restantes por columna:")
    print(df.isna().sum().to_string())
    print("\nTipos de datos:")
    print(df.dtypes.to_string())


if __name__ == "__main__":
    main()

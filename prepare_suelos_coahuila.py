from pathlib import Path
import pandas as pd


INPUT_PATH = Path("suelos_coahuila.csv")
MONTHLY_NASA_PATH = Path("data/processed/nasa_power_coahuila_monthly.csv")
OUTPUT_CSV = Path("data/processed/suelos_coahuila_clean.csv")
OUTPUT_JSON = Path("data/processed/suelos_coahuila_clean.json")

LOCATION_ID_MAP = {
    "La_Narro": "UAAAN_La_Narro",
    "Los_Lirios": "Los_Lirios_Arteaga",
    "General_Cepeda": "General_Cepeda",
}

ZONA_LABEL_MAP = {
    "La_Narro": "UAAAN La Narro (Saltillo)",
    "Los_Lirios": "Los Lirios (Arteaga)",
    "General_Cepeda": "General Cepeda",
}

TIPO_SUELO_LABEL_MAP = {
    "Xerosol_Calcico": "Xerosol Cálcico",
    "Feozem_Luvico": "Feozem Lúvico",
    "Regosol_Calcarico": "Regosol Calcárico",
}

ORDINAL_SCORES = {
    "Baja": 1,
    "Media": 2,
    "Alta": 3,
    "Muy_Alta": 4,
}


def main() -> None:
    df = pd.read_csv(INPUT_PATH, encoding="utf-8")

    # Strip extra whitespace in string columns and validate
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()

    assert len(df) == 3, f"Se esperaban 3 registros, se encontraron {len(df)}."
    assert df.isna().sum().sum() == 0, "Se encontraron valores nulos en suelos_coahuila.csv."

    # 2. Estandarización de llaves y etiquetas UI
    df["location_id"] = df["zona"].map(LOCATION_ID_MAP)
    df["zona_label"] = df["zona"].map(ZONA_LABEL_MAP)
    df["tipo_suelo_label"] = df["tipo_suelo"].map(TIPO_SUELO_LABEL_MAP)
    df["textura_label"] = df["textura"].str.replace("_", " ", regex=False)
    df["local_elevation_m"] = df["elevacion_msnm"].astype(float)

    # 3. Codificación numérica e indicadores de vulnerabilidad
    df["water_retention_score"] = df["retencion_agua"].map(ORDINAL_SCORES).astype(int)
    df["erosion_risk_score"] = df["riesgo_erosion"].map(ORDINAL_SCORES).astype(int)

    df["needs_nitrogen_fixation"] = (df["materia_organica_pct"] < 1.5).astype(int)
    df["needs_erosion_cover"] = (
        (df["erosion_risk_score"] >= 3) | (df["pendiente_pct"] >= 5.0)
    ).astype(int)
    df["high_drought_vulnerability"] = (df["water_retention_score"] == 1).astype(int)

    # 4. Entregables
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    df.to_json(OUTPUT_JSON, orient="records", indent=2, force_ascii=False)

    # Verificación de merge con nasa_power_coahuila_monthly.csv
    nasa_monthly = pd.read_csv(MONTHLY_NASA_PATH, encoding="utf-8")
    merged = nasa_monthly.merge(df, on="location_id", how="inner")

    print("=== VERIFICACIÓN DE SUELOS COAHUILA ===")
    print(
        df[
            [
                "location_id",
                "zona_label",
                "water_retention_score",
                "erosion_risk_score",
                "needs_nitrogen_fixation",
                "needs_erosion_cover",
                "high_drought_vulnerability",
            ]
        ].to_string(index=False)
    )
    print("\n=== MERGE DE PRUEBA CON NASA POWER MONTHLY ===")
    print(f"Filas en nasa_power_coahuila_monthly.csv: {len(nasa_monthly)}")
    print(f"Filas después del merge por location_id:  {len(merged)}")
    print(f"Cruce 100% exitoso sin pérdida de filas:  {len(nasa_monthly) == len(merged)}")


if __name__ == "__main__":
    main()

from pathlib import Path
import pandas as pd


INPUT_PATH = Path("cultivos_coahuila.csv")
OUTPUT_CSV = Path("data/processed/cultivos_coahuila_clean.csv")
OUTPUT_JSON = Path("data/processed/cultivos_coahuila_clean.json")

CULTIVO_LABELS = {
    "Maiz_Grano": "Maíz Grano",
    "Frijol_Pinto": "Frijol Pinto",
    "Avena_Forrajera": "Avena Forrajera",
    "Sorgo_Forrajero": "Sorgo Forrajero",
    "Alfalfa": "Alfalfa",
    "Cebada_Forrajera": "Cebada Forrajera",
}

CICLO_LABELS = {
    "Primavera-Verano": "Primavera-Verano",
    "Otono-Invierno": "Otoño-Invierno",
    "Todo_el_ano": "Todo el año",
}

ORDINAL_SCORES = {
    "Baja": 1,
    "Media": 2,
    "Alta": 3,
    "Muy_Alta": 4,
}

TARGET_SEASONS = {
    "Primavera-Verano": "Primavera,Verano",
    "Otono-Invierno": "Otoño,Invierno",
    "Todo_el_ano": "Primavera,Verano,Otoño,Invierno",
}

UMBRAL_HELADA = {
    1: 2.0,
    2: 1.0,
    3: 0.0,
    4: -2.0,
}

ECON_METRICS = {
    "Maiz_Grano": {"rendimiento_ton_ha": 4.5, "precio_ton_mxn": 6200, "costo_ha_mxn": 16500},
    "Frijol_Pinto": {"rendimiento_ton_ha": 1.4, "precio_ton_mxn": 21000, "costo_ha_mxn": 14000},
    "Avena_Forrajera": {"rendimiento_ton_ha": 18.0, "precio_ton_mxn": 1450, "costo_ha_mxn": 11500},
    "Sorgo_Forrajero": {"rendimiento_ton_ha": 22.0, "precio_ton_mxn": 1250, "costo_ha_mxn": 12000},
    "Alfalfa": {"rendimiento_ton_ha": 28.0, "precio_ton_mxn": 1850, "costo_ha_mxn": 24000},
    "Cebada_Forrajera": {"rendimiento_ton_ha": 16.5, "precio_ton_mxn": 1400, "costo_ha_mxn": 10800},
}


def main() -> None:
    df = pd.read_csv(INPUT_PATH, encoding="utf-8")

    # Strip extra whitespace in string columns and validate no nulls
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()

    assert df.isna().sum().sum() == 0, "Se encontraron valores nulos en el catálogo."
    assert (df["temp_min_c"] < df["temp_max_c"]).all(), "temp_min_c debe ser menor que temp_max_c."
    assert (df["consumo_agua_mm"] > 0).all(), "consumo_agua_mm debe ser mayor que 0."
    assert (df["profundidad_raiz_cm"] > 0).all(), "profundidad_raiz_cm debe ser mayor que 0."

    # 2. Normalización de etiquetas y puntajes agronómicos
    df["cultivo_label"] = df["cultivo"].map(CULTIVO_LABELS)
    df["ciclo_label"] = df["ciclo_siembra"].map(CICLO_LABELS)
    df["fija_nitrogeno_bin"] = df["fija_nitrogeno"].map({"Si": 1, "No": 0}).astype(int)

    df["erosion_control_score"] = df["reduce_erosion"].map(ORDINAL_SCORES).astype(int)
    df["drought_tolerance_score"] = df["tolerancia_sequia"].map(ORDINAL_SCORES).astype(int)
    df["frost_tolerance_score"] = df["tolerancia_heladas"].map(ORDINAL_SCORES).astype(int)

    df["target_seasons"] = df["ciclo_siembra"].map(TARGET_SEASONS)
    df["umbral_helada_c"] = df["frost_tolerance_score"].map(UMBRAL_HELADA).astype(float)

    # 3. Variables económicas
    df["rendimiento_ton_ha"] = df["cultivo"].map(lambda c: ECON_METRICS[c]["rendimiento_ton_ha"])
    df["precio_ton_mxn"] = df["cultivo"].map(lambda c: ECON_METRICS[c]["precio_ton_mxn"])
    df["costo_ha_mxn"] = df["cultivo"].map(lambda c: ECON_METRICS[c]["costo_ha_mxn"])

    df["ingreso_bruto_ha_mxn"] = df["rendimiento_ton_ha"] * df["precio_ton_mxn"]
    df["ingreso_neto_ha_mxn"] = df["ingreso_bruto_ha_mxn"] - df["costo_ha_mxn"]

    min_neto = df["ingreso_neto_ha_mxn"].min()
    max_neto = df["ingreso_neto_ha_mxn"].max()
    df["profit_score"] = (
        1 + 3 * (df["ingreso_neto_ha_mxn"] - min_neto) / (max_neto - min_neto)
    ).round().astype(int)

    # 4. Entregables
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    df.to_json(OUTPUT_JSON, orient="records", indent=2, force_ascii=False)

    cols_report = [
        "cultivo_label",
        "ingreso_neto_ha_mxn",
        "profit_score",
        "erosion_control_score",
        "drought_tolerance_score",
        "frost_tolerance_score",
        "fija_nitrogeno_bin",
    ]
    print("=== CATÁLOGO DE CULTIVOS COAHUILA (AGROSHIFT) ===")
    print(df[cols_report].to_string(index=False))


if __name__ == "__main__":
    main()

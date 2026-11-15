from src.agroshift_engine import simulate_scenarios


LOCATIONS = [
    "UAAAN_La_Narro",
    "Los_Lirios_Arteaga",
    "General_Cepeda",
]


def print_scenario_block(res: dict) -> None:
    rain_pct = int(round(res["rain_reduction_pct"] * 100))
    ctx = res["parcel_context"]
    w = res["normalized_weights"]

    print("=" * 112)
    print(
        f"PARCELA: {res['zona_label']} [{res['location_id']}] | Sup: {res['hectares']:.1f} ha | "
        f"Escenario Lluvia: -{rain_pct}% ({ctx['annual_simulated_rain_mm']} mm vs {ctx['annual_historical_rain_mm']} mm hist.)"
    )
    print(
        f"Suelo: {ctx['tipo_suelo_label']} ({ctx['textura_label']}) | Elev: {ctx['local_elevation_m']} msnm | "
        f"Pesos (Agua={w['weight_water']:.2f}, Rentab={w['weight_profit']:.2f}, Nitrógeno={w['weight_nitrogen']:.2f})"
    )
    print("-" * 112)
    header = (
        f"{'Plan de Rotación (3 Años)':<38} | {'Sequía':<8} | {'Helada':<8} | {'Plagas':<8} | "
        f"{'Ingreso Neto 3A':>15} | {'Ahorro Agua':>12} | {'N/Cob':>7} | {'Score':>6}"
    )
    print(header)
    print("-" * 112)

    for p in res["plans"]:
        ncob = (
            f"{p['balance_nitrogeno_y_cobertura']['ciclos_fijacion_nitrogeno_3a']}N/"
            f"{p['balance_nitrogeno_y_cobertura']['meses_suelo_protegido_3a']}m"
        )
        winner_mark = " ★" if p["plan_id"] == res["recommended_plan_id"] else "  "
        print(
            f"{p['plan_name']:<38} | "
            f"{p['semaforo_sequia']:<8} | "
            f"{p['semaforo_heladas']:<8} | "
            f"{p['semaforo_plagas']:<8} | "
            f"${p['ingreso_neto_total_mxn']:>14,.0f} | "
            f"{p['ahorro_agua_m3']:>10,.0f} m³ | "
            f"{ncob:>7} | "
            f"{p['suitability_score']:>5.1f}{winner_mark}"
        )

    print("-" * 112)
    print(
        f"RECOMENDACIÓN AGROSHIFT: {res['recommended_plan_name']} "
        f"(Score: {res['recommended_suitability_score']:.2f}/100)"
    )
    for p in res["plans"]:
        print(f"  • [{p['plan_id']}] {p['nasa_evidence_summary']}")
    print()


def run_tests() -> None:
    print("\n>>> SIMULACIÓN COMPARATIVA AGROSHIFT: LLUVIA NORMAL (0%) VS SEQUÍA EXTREMA (-20%) <<<\n")

    for loc_id in LOCATIONS:
        res_normal = simulate_scenarios(
            location_id=loc_id,
            hectares=10.0,
            weight_water=0.33,
            weight_profit=0.33,
            weight_nitrogen=0.34,
            rain_reduction_pct=0.0,
        )
        print_scenario_block(res_normal)

        res_drought = simulate_scenarios(
            location_id=loc_id,
            hectares=10.0,
            weight_water=0.33,
            weight_profit=0.33,
            weight_nitrogen=0.34,
            rain_reduction_pct=0.20,
        )
        print_scenario_block(res_drought)

        # Verificaciones lógicas (assertions)
        plan_actual_norm = res_normal["plans"][0]
        plan_actual_drought = res_drought["plans"][0]
        plan_conserv_drought = res_drought["plans"][1]
        plan_regen_drought = res_drought["plans"][2]

        # 1. La sequía de -20% incrementa el índice de estrés hídrico en todos los planes
        assert (
            plan_actual_drought["years"][0]["drought_stress_index"]
            > plan_actual_norm["years"][0]["drought_stress_index"]
        ), f"El estrés hídrico no subió con -20% lluvia en {loc_id}"

        # 2. Penalización de monocultivo (+35% Año 2, +70% Año 3 en Plan Actual)
        assert plan_actual_norm["years"][0]["pest_multiplier"] == 1.00
        assert plan_actual_norm["years"][1]["pest_multiplier"] == 1.35
        assert plan_actual_norm["years"][2]["pest_multiplier"] == 1.70

        # 3. Ahorro de agua positivo en Plan Conservación Hídrica respecto a Plan Actual
        assert plan_conserv_drought["ahorro_agua_m3"] > 0, f"Ahorro de agua debe ser > 0 en {loc_id}"

        # 4. Los planes alternativos protegen los 36 meses frente a 18 meses del Plan Actual
        assert plan_actual_norm["balance_nitrogeno_y_cobertura"]["meses_suelo_desnudo_3a"] == 18
        assert plan_conserv_drought["balance_nitrogeno_y_cobertura"]["meses_suelo_protegido_3a"] == 36
        assert plan_regen_drought["balance_nitrogeno_y_cobertura"]["meses_suelo_protegido_3a"] == 36

    # Prueba de sensibilidad de sliders de prioridad en UAAAN_La_Narro (-20% lluvia)
    print("=" * 112)
    print("PRUEBA DE SENSIBILIDAD DE SLIDERS DE PRIORIDAD (UAAAN_La_Narro | 10 ha | -20% Lluvia)")
    print("-" * 112)
    slider_profiles = [
        ("Prioridad Cuidado del Agua (0.80, 0.10, 0.10)", (0.80, 0.10, 0.10)),
        ("Prioridad Maximizar Ingresos (0.10, 0.80, 0.10)", (0.10, 0.80, 0.10)),
        ("Prioridad Regeneración/Nitrógeno (0.10, 0.10, 0.80)", (0.10, 0.10, 0.80)),
    ]
    for label, (ww, wp, wn) in slider_profiles:
        sim = simulate_scenarios(
            location_id="UAAAN_La_Narro",
            hectares=10.0,
            weight_water=ww,
            weight_profit=wp,
            weight_nitrogen=wn,
            rain_reduction_pct=0.20,
        )
        scores_str = " | ".join(
            f"{p['plan_name']}: {p['suitability_score']:.1f}" for p in sim["plans"]
        )
        print(f"• {label:<50} -> GANA: {sim['recommended_plan_name']} ({scores_str})")
    print("=" * 112)
    print("TODAS LAS ASERCIONES Y PRUEBAS DE SIMULACIÓN PASARON EXITOSAMENTE.")


if __name__ == "__main__":
    run_tests()

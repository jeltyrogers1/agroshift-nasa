/* AgroShift — Mobile-First 5-Step Wizard Controller (Vanilla ES6 + Leaflet + Chart.js) */
(() => {
  const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const CURRENCY = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
  const NUM = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 });
  const DEC1 = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const DEFAULT_HA = 10;
  const MAX_HA = 50000;
  const LITERS_PER_HA_REF = 7900000;
  const TOTAL_STEPS = 6;

  const LIGHT_LABELS = { VERDE: "Bajo", AMARILLO: "Medio", ROJO: "Alto" };

  const SOIL_TIPS = {
    "Xerosol Cálcico":
      "Xerosol Cálcico: suelo de zona semiárida rico en calcio, con capa superficial clara y poca materia orgánica; requiere conservar humedad y rastrojo.",
    "Feozem Lúvico":
      "Feozem Lúvico: suelo oscuro de montaña, más rico en materia orgánica y arcillas; retiene mejor la humedad y los nutrientes.",
    "Regosol Calcárico":
      "Regosol Calcárico: suelo joven y poco profundo sobre material calcáreo; drena rápido y necesita coberturas vegetales para evitar erosión.",
  };

  const NEXT_BUTTON_LABELS = {
    1: "Comenzar Diagnóstico",
    2: "Siguiente: Tu Cultivo",
    3: "Siguiente: Fertilización",
    4: "Calcular Diagnóstico NASA",
    5: "Ver Soluciones Recomendadas",
    6: "Exportar Plan para Campo",
  };

  const state = {
    currentStep: 1,
    suelos: {},
    cultivos: [],
    climatology: {},
    historyByLocation: {},
    locationId: "UAAAN_La_Narro",
    hectares: DEFAULT_HA,
    fromPolygon: false,
    cappedWarning: false,
    wWater: 33,
    wProfit: 33,
    wNitrogen: 34,
    rainPct: 0,
    tempIncreaseC: 0.0,
    irrigationMode: "temporal",
    marketGoal: "grano",
    currentCrop: "Maiz_Grano",
    customCropName: "",
    customCropWaterTier: "medio",
    fertilizerType: "quimico",
    tillageMode: "convencional",
    mainConcerns: ["sequia"],
    editingSoil: false,
    soilOverride: null,
    activeMapLayer: "aerial",
    chartMode: "seasonal",
    lastSimResult: null,
  };

  let map,
    parcelMarker,
    drawnItems,
    esriSatLayer,
    gibsLstLayer,
    chart,
    debounceTimer;
  let reqSeq = 0;

  const $ = (id) => document.getElementById(id);
  const icons = () =>
    window.lucide &&
    window.lucide.createIcons({
      attrs: { "stroke-width": 2.25 },
    });

  function tipBadge(text, alignRight = false) {
    return `<span class="tip ${alignRight ? "tip-right" : ""
      }" tabindex="0"><button type="button" class="tip-btn" aria-label="Explicación agronómica">?</button><span class="tip-text">${text}</span></span>`;
  }

  function computeWaterGoalLiters() {
    return Math.round((state.wWater / 100) * state.hectares * LITERS_PER_HA_REF);
  }

  function updateWaterOutput() {
    const el = $("out-water");
    if (el) el.textContent = `${NUM.format(computeWaterGoalLiters())} L`;
  }

  /* ---------- Wizard Step Navigation ---------- */
  function goToStep(stepNum) {
    const target = Math.max(1, Math.min(TOTAL_STEPS, Number(stepNum)));
    state.currentStep = target;

    for (let i = 1; i <= TOTAL_STEPS; i++) {
      const sec = $(`step-${i}`);
      if (sec) sec.classList.toggle("hidden", i !== target);
    }

    $("step-counter").textContent = `Paso ${target} de ${TOTAL_STEPS}`;
    $("step-progress-fill").style.width = `${(target / TOTAL_STEPS) * 100}%`;

    document.querySelectorAll(".step-pill[data-goto]").forEach((btn) => {
      const s = Number(btn.dataset.goto);
      btn.classList.toggle("active", s === target);
      btn.classList.toggle("done", s < target);
    });

    const prevBtn = $("btn-prev");
    const nextLbl = $("btn-next-label");
    prevBtn.classList.toggle("hidden", target === 1);
    nextLbl.textContent = NEXT_BUTTON_LABELS[target];

    if (target === 2) {
      setTimeout(() => {
        if (map) map.invalidateSize();
      }, 60);
    } else if (target === 5) {
      simulate();
      setTimeout(() => {
        renderChart();
        if (chart) chart.resize();
      }, 60);
    } else if (target === 6) {
      if (!state.lastSimResult) {
        simulate();
      } else {
        renderSolutions(state.lastSimResult);
      }
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
    icons();
  }

  /* ---------- Step 2: Tabs, Map & Soil ---------- */
  function renderTabs() {
    const nav = $("plot-tabs");
    nav.innerHTML = Object.values(state.suelos)
      .map((s) => {
        const active = s.location_id === state.locationId;
        return `
        <button type="button" data-loc="${s.location_id}" class="zone-btn ${active ? "active" : ""}">
          <div>
            <div class="font-display font-bold text-sm text-slate-900">${s.zona_label || s.display_name}</div>
            <div class="text-xs text-slate-500">${s.municipio} · ${s.tipo_suelo_label} · ${NUM.format(
          s.elevacion_msnm || 0
        )} msnm</div>
          </div>
          <div class="w-6 h-6 rounded-full flex items-center justify-center ${active ? "bg-[#15803D] text-white" : "bg-slate-100 text-slate-400"
          }">
            <i data-lucide="check" class="w-3.5 h-3.5"></i>
          </div>
        </button>`;
      })
      .join("");

    nav.querySelectorAll("button").forEach((btn) =>
      btn.addEventListener("click", () => selectLocation(btn.dataset.loc))
    );

    const activeSoil = state.suelos[state.locationId];
    if (activeSoil && $("header-parcel-label")) {
      $("header-parcel-label").textContent = `${activeSoil.zona_label} · ${NUM.format(state.hectares)} ha`;
    }
    icons();
  }

  function renderCropSelector() {
    const sel = $("select-crop");
    if (!sel || !Array.isArray(state.cultivos) || !state.cultivos.length) return;
    sel.innerHTML =
      state.cultivos
        .map(
          (c) => `<option value="${c.cultivo}">${c.cultivo_label} (${c.ciclo_label || c.ciclo_siembra})</option>`
        )
        .join("") + `<option value="__otro__">Otro (Escribir manualmente)...</option>`;
    sel.value = state.currentCrop;
    const customBox = $("custom-crop-box");
    if (customBox) customBox.classList.toggle("hidden", state.currentCrop !== "__otro__");
  }

  function inferCustomCropWaterTier(rawName) {
    const q = String(rawName || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
    if (!q.trim()) return null;
    const highKeywords = ["papa", "manzana", "nuez", "nogal", "tomate", "chile", "cebolla", "lechuga", "fresa", "sandia", "melon"];
    const midKeywords = ["trigo", "girasol", "calabaza", "garbanzo", "soya", "lenteja", "cartamo"];
    const lowKeywords = ["zacate", "mijo", "nopal", "maguey", "agave", "pasto"];
    if (highKeywords.some((kw) => q.includes(kw))) return "alto";
    if (midKeywords.some((kw) => q.includes(kw))) return "medio";
    if (lowKeywords.some((kw) => q.includes(kw))) return "bajo";
    return null;
  }

  function inferSoilScoresFromText(typeText, texText, currentWRet, currentERisk, sourceField) {
    const t = String(typeText || "").toLowerCase();
    const x = String(texText || "").toLowerCase();
    const combined = `${t} ${x}`;
    let wRet = currentWRet;
    let eRisk = currentERisk;

    if (sourceField === "type-text") {
      if (t.includes("aren") || t.includes("regosol")) {
        wRet = 1;
        eRisk = 3;
      } else if (t.includes("arcill") || t.includes("vertisol")) {
        wRet = 3;
        eRisk = 1;
      } else if (t.includes("feozem") || t.includes("negra") || t.includes("aluvial") || t.includes("castañ") || t.includes("castan")) {
        wRet = 3;
      } else if (t.includes("xerosol")) {
        wRet = 2;
      }
    } else if (sourceField === "tex-text") {
      if (x.includes("aren")) {
        wRet = 1;
        eRisk = 3;
      } else if (x.includes("limo") && x.includes("arcill")) {
        wRet = 3;
        eRisk = 3;
      } else if (x.includes("limo")) {
        eRisk = 3;
      } else if (x.includes("arcill")) {
        wRet = 3;
        eRisk = x.includes("franco") ? 2 : 1;
      }
    } else {
      if (combined.includes("aren") || combined.includes("regosol")) {
        wRet = 1;
        eRisk = 3;
      } else if (combined.includes("arcill") || combined.includes("vertisol")) {
        wRet = 3;
        eRisk = combined.includes("limo") ? 3 : 1;
      } else if (combined.includes("limo")) {
        eRisk = 3;
      }
    }

    return { wRet, eRisk };
  }

  function buildDynamicSoilProblem(s, isCustom) {
    if (!isCustom) return `Diagnóstico local: ${s.problema_principal}`;
    const issues = [];
    const mo = Number(s.materia_organica_pct);
    const slope = Number(s.pendiente_pct);
    const wRet = Number(s.water_retention_score);
    const eRisk = Number(s.erosion_risk_score);
    const customName = `${s.tipo_suelo_label || "Suelo"} (${s.textura_label || "textura local"})`;

    if (mo < 1.5) {
      issues.push(`baja materia orgánica (${mo.toFixed(1)}% MO < 1.5%, urge fijar nitrógeno e incorporar rastrojo)`);
    }
    if (slope >= 5.0) {
      issues.push(`pendiente pronunciada (${slope.toFixed(1)}% >= 5%, alto riesgo de escorrentía y arrastre de suelo)`);
    }
    if (wRet === 1) {
      issues.push("baja retención de humedad superficial");
    }
    if (eRisk === 3 && slope < 5.0) {
      issues.push(`alta susceptibilidad a erosión en textura ${(s.textura_label || "").toLowerCase()}`);
    }
    if (!issues.length) {
      return `Diagnóstico en campo (${customName}): Suelo equilibrado (${mo.toFixed(1)}% MO, pendiente ${slope.toFixed(1)}%) con buena capacidad productiva; se recomienda mantener cobertura orgánica.`;
    }
    return `Diagnóstico en campo (${customName}): Atención prioritaria por ${issues.join("; ")}.`;
  }

  function getEffectiveSoil() {
    const base = state.suelos[state.locationId];
    if (!base) return null;
    if (!state.soilOverride) return { ...base, is_custom: false };
    const ov = state.soilOverride;
    const wRet = Number(ov.water_retention_score ?? base.water_retention_score ?? 2);
    const eRisk = Number(ov.erosion_risk_score ?? base.erosion_risk_score ?? 2);
    const retMap = { 1: "Baja", 2: "Media", 3: "Alta" };
    const eroMap = { 1: "Bajo", 2: "Medio", 3: "Alto" };
    const merged = {
      ...base,
      tipo_suelo_label: ov.tipo_suelo_label || base.tipo_suelo_label,
      textura_label: ov.textura_label || base.textura_label,
      water_retention_score: wRet,
      retencion_agua: retMap[wRet] || base.retencion_agua,
      erosion_risk_score: eRisk,
      riesgo_erosion: eroMap[eRisk] || base.riesgo_erosion,
      materia_organica_pct: Number(ov.materia_organica_pct ?? base.materia_organica_pct),
      local_elevation_m: Number(ov.local_elevation_m ?? base.local_elevation_m ?? base.elevacion_msnm),
      elevacion_msnm: Number(ov.local_elevation_m ?? base.elevacion_msnm),
      pendiente_pct: Number(ov.pendiente_pct ?? base.pendiente_pct),
      is_custom: true,
    };
    return merged;
  }

  function renderSoil() {
    const s = getEffectiveSoil();
    if (!s) return;
    const isCustom = Boolean(state.soilOverride);

    const badgeEl = $("soil-custom-badge");
    if (badgeEl) badgeEl.classList.toggle("hidden", !isCustom);

    const resetBtn = $("btn-reset-soil");
    if (resetBtn) resetBtn.classList.toggle("hidden", !isCustom && !state.editingSoil);

    const editBtn = $("btn-edit-soil");
    if (editBtn) {
      editBtn.innerHTML = state.editingSoil
        ? `<i data-lucide="check" class="w-3 h-3"></i><span>Listo</span>`
        : `<i data-lucide="pencil" class="w-3 h-3"></i><span>Editar datos</span>`;
    }

    const soilType = s.tipo_suelo_label || s.soil_type || "";
    const textura = s.textura_label || s.textura || "";
    const soilTip =
      SOIL_TIPS[soilType] ||
      "Clasificación FAO/INEGI o nombre local que indica la capacidad del suelo para retener agua y nutrientes.";
    const moTip =
      "Materia Orgánica (MO): porcentaje de carbono vegetal y humus en el suelo. A mayor MO, el suelo funciona como esponja que retiene lluvia y fertilidad.";

    if (!state.editingSoil) {
      const items = [
        ["Tipo de suelo", soilType, `Retención: ${s.retencion_agua}`, tipBadge(soilTip)],
        ["Textura", textura, `Erosión: ${s.riesgo_erosion}`, ""],
        [
          "Materia Orgánica",
          `${Number(s.materia_organica_pct).toFixed(1)}% MO`,
          Number(s.materia_organica_pct) < 1.5 ? "Nivel crítico (< 1.5%)" : "Fertilidad natural",
          tipBadge(moTip),
        ],
        [
          "Altitud y Pendiente",
          `${NUM.format(s.elevacion_msnm || 0)} msnm`,
          `Pendiente ${Number(s.pendiente_pct).toFixed(1)}%`,
          "",
        ],
      ];

      $("soil-metrics").innerHTML = items
        .map(
          ([k, v, sub, tip]) => `
        <div class="soil-cell">
          <div class="lbl flex items-center">${k}${tip}</div>
          <div class="val truncate" title="${v}">${v}</div>
          <div class="text-[11px] text-slate-500 mt-0.5 truncate">${sub}</div>
        </div>`
        )
        .join("");
      $("soil-problem").textContent = buildDynamicSoilProblem(s, isCustom);
      icons();
      return;
    }

    // Modo edición: Selectores estándar (<select>) con opción de escritura manual + Selectores compactos
    const SOIL_TYPE_OPTIONS = [
      "Xerosol Cálcico",
      "Feozem Lúvico",
      "Regosol Calcárico",
      "Vertisol Pélico",
      "Castañozem",
      "Tierra Negra / Aluvial",
    ];
    const SOIL_TEX_OPTIONS = [
      "Franco Arcilloso",
      "Franco Limoso",
      "Franco Arenoso",
      "Arcilloso Pesado",
      "Arenoso",
    ];

    const escapeAttr = (val) => String(val || "").replace(/"/g, "&quot;");
    const renderSelectWithCustom = (selectKey, inputKey, options, currentVal, placeholder) => {
      const isPreset = options.includes(currentVal);
      const selectedVal = isPreset ? currentVal : "__otro__";
      const customVal = isPreset ? "" : currentVal;
      const optionsHtml = options
        .map(
          (opt) =>
            `<option value="${escapeAttr(opt)}" ${selectedVal === opt ? "selected" : ""}>${opt}</option>`
        )
        .join("");

      return `
        <select data-soil-field="${selectKey}" class="bg-white border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-800 w-full">
          ${optionsHtml}
          <option value="__otro__" ${selectedVal === "__otro__" ? "selected" : ""}>Otro (Escribir manualmente)...</option>
        </select>
        <input data-soil-field="${inputKey}" type="text" autocomplete="off" value="${escapeAttr(customVal)}" placeholder="${escapeAttr(placeholder)}" class="bg-white border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-800 w-full ${selectedVal === "__otro__" ? "" : "hidden"}" />
      `;
    };

    const wScore = Number(s.water_retention_score || 2);
    const eScore = Number(s.erosion_risk_score || 2);

    $("soil-metrics").innerHTML = `
      <div class="soil-cell space-y-1.5">
        <label class="lbl block">Tipo de suelo</label>
        ${renderSelectWithCustom("type-select", "type-text", SOIL_TYPE_OPTIONS, soilType, "Escribe el tipo de suelo")}
        <div class="flex items-center justify-between gap-1.5 pt-0.5">
          <span class="text-[10px] font-semibold text-slate-500 shrink-0">Retención agua:</span>
          <select data-soil-field="ret-score" class="soil-select py-1 px-2 text-[11px] min-h-[30px]">
            <option value="1" ${wScore === 1 ? "selected" : ""}>Baja</option>
            <option value="2" ${wScore === 2 ? "selected" : ""}>Media</option>
            <option value="3" ${wScore === 3 ? "selected" : ""}>Alta</option>
          </select>
        </div>
      </div>

      <div class="soil-cell space-y-1.5">
        <label class="lbl block">Textura</label>
        ${renderSelectWithCustom("tex-select", "tex-text", SOIL_TEX_OPTIONS, textura, "Escribe la textura")}
        <div class="flex items-center justify-between gap-1.5 pt-0.5">
          <span class="text-[10px] font-semibold text-slate-500 shrink-0">Riesgo erosión:</span>
          <select data-soil-field="ero-score" class="soil-select py-1 px-2 text-[11px] min-h-[30px]">
            <option value="1" ${eScore === 1 ? "selected" : ""}>Bajo</option>
            <option value="2" ${eScore === 2 ? "selected" : ""}>Medio</option>
            <option value="3" ${eScore === 3 ? "selected" : ""}>Alto</option>
          </select>
        </div>
      </div>

      <div class="soil-cell space-y-1">
        <label class="lbl block">Materia Orgánica (% MO)</label>
        <input data-soil-field="mo" type="number" min="0.1" max="10.0" step="0.1" value="${Number(
      s.materia_organica_pct
    ).toFixed(1)}" class="soil-input" />
        <div class="text-[10px] text-slate-400">Rango 0.1% – 10.0%</div>
      </div>

      <div class="soil-cell space-y-1">
        <label class="lbl block">Altitud (msnm) y Pendiente (%)</label>
        <div class="grid grid-cols-2 gap-1.5">
          <div>
            <input data-soil-field="elev" type="number" min="500" max="3500" step="10" value="${Math.round(
      Number(s.elevacion_msnm || 1500)
    )}" class="soil-input" title="Altitud msnm" />
            <span class="text-[9px] text-slate-400 block mt-0.5">msnm</span>
          </div>
          <div>
            <input data-soil-field="slope" type="number" min="0.0" max="30.0" step="0.5" value="${Number(
      s.pendiente_pct || 2.0
    ).toFixed(1)}" class="soil-input" title="Pendiente %" />
            <span class="text-[9px] text-slate-400 block mt-0.5">% pend.</span>
          </div>
        </div>
      </div>
    `;

    $("soil-problem").textContent = buildDynamicSoilProblem(s, isCustom);

    const container = $("soil-metrics");
    const syncCustomInputVisibility = (selEl, inpEl, shouldFocus) => {
      if (!selEl || !inpEl) return;
      const isCustomOption = selEl.value === "__otro__";
      inpEl.classList.toggle("hidden", !isCustomOption);
      if (isCustomOption && shouldFocus) inpEl.focus();
    };
    const resolveSelectValue = (selEl, inpEl) =>
      (selEl && selEl.value === "__otro__" ? (inpEl ? inpEl.value : "") : selEl ? selEl.value : "").trim();

    const onFieldChange = (ev) => {
      const typeSel = container.querySelector('[data-soil-field="type-select"]');
      const typeInp = container.querySelector('[data-soil-field="type-text"]');
      const retSel = container.querySelector('[data-soil-field="ret-score"]');
      const texSel = container.querySelector('[data-soil-field="tex-select"]');
      const texInp = container.querySelector('[data-soil-field="tex-text"]');
      const eroSel = container.querySelector('[data-soil-field="ero-score"]');
      const moInp = container.querySelector('[data-soil-field="mo"]');
      const elevInp = container.querySelector('[data-soil-field="elev"]');
      const slopeInp = container.querySelector('[data-soil-field="slope"]');

      const sourceField = ev?.target?.getAttribute("data-soil-field") || "";
      if (sourceField === "type-select") {
        syncCustomInputVisibility(typeSel, typeInp, ev?.type === "change");
      } else if (sourceField === "tex-select") {
        syncCustomInputVisibility(texSel, texInp, ev?.type === "change");
      }

      const rawType = resolveSelectValue(typeSel, typeInp);
      const rawTex = resolveSelectValue(texSel, texInp);

      let wScoreNum = Number(retSel ? retSel.value : 2) || 2;
      let eScoreNum = Number(eroSel ? eroSel.value : 2) || 2;

      // Auto-detección amigable cuando el usuario elige o escribe en tipo de suelo o textura
      const inferSource =
        sourceField === "type-select" || sourceField === "type-text"
          ? "type-text"
          : sourceField === "tex-select" || sourceField === "tex-text"
          ? "tex-text"
          : "";
      if (inferSource) {
        const inferred = inferSoilScoresFromText(rawType, rawTex, wScoreNum, eScoreNum, inferSource);
        wScoreNum = inferred.wRet;
        eScoreNum = inferred.eRisk;
        if (retSel) retSel.value = String(wScoreNum);
        if (eroSel) eroSel.value = String(eScoreNum);
      }

      const baseSoil = state.suelos[state.locationId] || {};
      const tLabel = rawType || baseSoil.tipo_suelo_label || "Suelo Local";
      const xLabel = rawTex || baseSoil.textura_label || "Textura Local";
      const moVal = Math.min(10.0, Math.max(0.1, parseFloat(moInp?.value) || 1.4));
      const elevVal = Math.min(3500, Math.max(500, parseFloat(elevInp?.value) || 1600));
      const slopeVal = Math.min(30.0, Math.max(0.0, parseFloat(slopeInp?.value) || 0.0));

      state.soilOverride = {
        tipo_suelo_label: tLabel,
        water_retention_score: wScoreNum,
        textura_label: xLabel,
        erosion_risk_score: eScoreNum,
        materia_organica_pct: +moVal.toFixed(1),
        local_elevation_m: Math.round(elevVal),
        pendiente_pct: +slopeVal.toFixed(1),
      };

      const eff = getEffectiveSoil();
      if (badgeEl) badgeEl.classList.remove("hidden");
      if (resetBtn) resetBtn.classList.remove("hidden");
      $("soil-problem").textContent = buildDynamicSoilProblem(eff, true);
      updateMapMarker(false);
      scheduleSimulate(150);
    };

    container.querySelectorAll("[data-soil-field]").forEach((el) => {
      if (el.tagName === "SELECT") {
        el.addEventListener("change", onFieldChange);
      } else {
        el.addEventListener("input", onFieldChange);
        el.addEventListener("change", onFieldChange);
      }
    });

    icons();
  }

  const GIBS_LST_DATE = "2026-05-15";

  function renderMapLayerLegend() {
    const legendEl = $("map-layer-legend");
    if (!legendEl) return;

    if (state.activeMapLayer === "lst") {
      legendEl.innerHTML = `
        <div class="space-y-2">
          <div class="flex items-center justify-between text-[11px] font-bold text-slate-800">
            <span>Estrés Térmico (NASA Temperatura Superficial)</span>
            <span class="text-[10px] font-semibold text-rose-800 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200">${GIBS_LST_DATE}</span>
          </div>
          <div class="legend-gradient-lst w-full"></div>
          <div class="grid grid-cols-3 gap-1.5 text-[10.5px] leading-tight pt-0.5">
            <div><strong class="text-sky-700">Azul / Cian:</strong> <span class="text-slate-600">Superficie fresca (zonas altas o húmedas).</span></div>
            <div class="text-center"><strong class="text-amber-600">Amarillo / Naranja:</strong> <span class="text-slate-600">Temperatura templada a cálida.</span></div>
            <div class="text-right"><strong class="text-rose-700">Rojo / Magenta:</strong> <span class="text-slate-600">Alto calor superficial y mayor evaporación.</span></div>
          </div>
        </div>
      `;
    } else {
      legendEl.innerHTML = `
        <div class="flex items-center gap-2 text-slate-600">
          <i data-lucide="satellite" class="w-4 h-4 text-[#0F5132] shrink-0"></i>
          <span>Imagen satelital de alta resolución para ubicar tu parcela y trazar sus bordes.</span>
        </div>
      `;
    }
    icons();
  }

  function setMapLayer(layerKey) {
    state.activeMapLayer = layerKey;
    const tabsBox = $("nasa-layer-tabs");
    if (tabsBox) {
      tabsBox.querySelectorAll("button[data-layer]").forEach((btn) => {
        const isActive = btn.dataset.layer === layerKey;
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    }

    if (map) {
      if (gibsLstLayer && map.hasLayer(gibsLstLayer)) map.removeLayer(gibsLstLayer);

      if (layerKey === "lst" && gibsLstLayer) {
        gibsLstLayer.setOpacity(0.70);
        gibsLstLayer.addTo(map);
      }

      if (drawnItems && typeof drawnItems.bringToFront === "function") {
        drawnItems.bringToFront();
      }
      if (parcelMarker && typeof parcelMarker.bringToFront === "function") {
        parcelMarker.bringToFront();
      }
    }

    renderMapLayerLegend();
  }

  function initMap() {
    const s = state.suelos[state.locationId];
    map = L.map("map", { zoomControl: true, maxZoom: 18 }).setView([s.latitud, s.longitud], 14);

    if (map.getPane("overlayPane")) map.getPane("overlayPane").style.zIndex = "600";
    if (map.getPane("markerPane")) map.getPane("markerPane").style.zIndex = "650";
    if (map.getPane("popupPane")) map.getPane("popupPane").style.zIndex = "700";

    esriSatLayer = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Tiles &copy; Esri", maxZoom: 18, zIndex: 100 }
    );
    esriSatLayer.addTo(map);

    gibsLstLayer = L.tileLayer(
      `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_Land_Surface_Temp_Day/default/${GIBS_LST_DATE}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png`,
      {
        maxZoom: 18,
        maxNativeZoom: 7,
        opacity: 0.70,
        zIndex: 400,
        attribution: "NASA GIBS · MODIS Terra LST",
      }
    );

    drawnItems = new L.FeatureGroup().addTo(map);

    const drawControl = new L.Control.Draw({
      position: "topleft",
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: true,
          shapeOptions: { color: "#15803d", fillColor: "#22c55e", fillOpacity: 0.28, weight: 2 },
        },
        rectangle: {
          shapeOptions: { color: "#15803d", fillColor: "#22c55e", fillOpacity: 0.28, weight: 2 },
        },
        polyline: false,
        circle: false,
        marker: false,
        circlemarker: false,
      },
      edit: { featureGroup: drawnItems },
    });
    map.addControl(drawControl);

    map.on(L.Draw.Event.CREATED, (e) => {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);
      if (typeof drawnItems.bringToFront === "function") drawnItems.bringToFront();
      applyLayerArea(e.layer);
    });
    map.on(L.Draw.Event.EDITED, (e) => {
      e.layers.eachLayer((layer) => applyLayerArea(layer));
    });
    map.on(L.Draw.Event.DELETED, () => {
      if (drawnItems.getLayers().length === 0) {
        clearPolygonState();
      }
    });

    $("btn-clear-poly").addEventListener("click", () => {
      if (drawnItems) drawnItems.clearLayers();
      clearPolygonState();
    });

    const layerTabs = $("nasa-layer-tabs");
    if (layerTabs) {
      layerTabs.querySelectorAll("button[data-layer]").forEach((btn) => {
        btn.addEventListener("click", () => {
          setMapLayer(btn.dataset.layer);
        });
      });
    }

    renderMapLayerLegend();
    updateMapMarker(false);
  }

  function clearPolygonState() {
    state.fromPolygon = false;
    state.cappedWarning = false;
    $("poly-info").classList.add("hidden");
    $("btn-clear-poly").classList.add("hidden");
    setHectares(DEFAULT_HA, false);
  }

  function findNearestStation(lat, lon) {
    let bestId = state.locationId;
    let bestDist = Infinity;
    Object.values(state.suelos).forEach((s) => {
      const d = Math.hypot(s.latitud - lat, s.longitud - lon);
      if (d < bestDist) {
        bestDist = d;
        bestId = s.location_id;
      }
    });
    return bestId;
  }

  function applyLayerArea(layer) {
    let areaM2 = 0;
    if (window.turf && typeof layer.toGeoJSON === "function") {
      areaM2 = window.turf.area(layer.toGeoJSON());
    } else if (L.GeometryUtil && typeof layer.getLatLngs === "function") {
      areaM2 = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
    }
    const rawHa = Math.max(0.5, +(areaM2 / 10000).toFixed(1));

    if (typeof layer.getBounds === "function") {
      const center = layer.getBounds().getCenter();
      const nearest = findNearestStation(center.lat, center.lng);
      if (nearest !== state.locationId) {
        state.locationId = nearest;
        state.soilOverride = null;
        state.editingSoil = false;
        renderTabs();
        renderSoil();
        renderChart();
      }
    }

    state.fromPolygon = true;
    $("btn-clear-poly").classList.remove("hidden");
    if (rawHa > MAX_HA) {
      state.cappedWarning = true;
      setHectares(MAX_HA, true);
    } else {
      state.cappedWarning = false;
      setHectares(rawHa, true);
    }
  }

  function updateMapMarker(fly = true) {
    const s = getEffectiveSoil() || state.suelos[state.locationId];
    if (!map || !s) return;
    if (parcelMarker) map.removeLayer(parcelMarker);
    parcelMarker = L.circleMarker([s.latitud, s.longitud], {
      radius: 9,
      color: "#ffffff",
      weight: 2.5,
      fillColor: "#15803d",
      fillOpacity: 1,
    })
      .addTo(map)
      .bindPopup(`<b>${s.zona_label}</b><br>${s.tipo_suelo_label} · MO ${s.materia_organica_pct}%`);
    if (typeof parcelMarker.bringToFront === "function") parcelMarker.bringToFront();
    if (fly) map.flyTo([s.latitud, s.longitud], 14, { duration: 0.9 });
  }

  function setHectares(val, fromPoly) {
    const clamped = Math.min(MAX_HA, Math.max(0.5, +Number(val).toFixed(1)));
    state.hectares = clamped;
    state.fromPolygon = fromPoly;
    $("input-ha").value = state.hectares;

    const s = state.suelos[state.locationId];
    const stationName = s ? s.zona_label : state.locationId;
    if (s && $("header-parcel-label")) {
      $("header-parcel-label").textContent = `${s.zona_label} · ${NUM.format(state.hectares)} ha`;
    }

    const polyInfo = $("poly-info");
    if (fromPoly || state.cappedWarning) {
      polyInfo.classList.remove("hidden");
      polyInfo.textContent = state.cappedWarning
        ? `Aviso: Polígono limitado al tope realista de ${NUM.format(MAX_HA)} ha · Estación: ${stationName}.`
        : `Polígono medido: ${DEC1.format(state.hectares)} ha · Estación más cercana: ${stationName}.`;
    } else {
      polyInfo.classList.add("hidden");
    }
    updateWaterOutput();
    scheduleSimulate();
  }

  function selectLocation(locId) {
    state.locationId = locId;
    state.soilOverride = null;
    state.editingSoil = false;
    if (drawnItems) drawnItems.clearLayers();
    state.fromPolygon = false;
    state.cappedWarning = false;
    $("poly-info").classList.add("hidden");
    $("btn-clear-poly").classList.add("hidden");
    setHectares(DEFAULT_HA, false);
    renderTabs();
    renderSoil();
    updateMapMarker(true);
    renderChart();
    scheduleSimulate(40);
  }

  /* ---------- Controls ---------- */
  function bindControls() {
    // Botones de navegación del Wizard
    $("btn-prev").addEventListener("click", () => {
      if (state.currentStep > 1) goToStep(state.currentStep - 1);
    });
    $("btn-next").addEventListener("click", () => {
      if (state.currentStep < TOTAL_STEPS) {
        goToStep(state.currentStep + 1);
      } else {
        renderPrintSheet();
        window.print();
      }
    });
    document.querySelectorAll(".step-pill[data-goto]").forEach((btn) => {
      btn.addEventListener("click", () => goToStep(Number(btn.dataset.goto)));
    });

    // Prioridades del agricultor
    $("sl-water").addEventListener("input", (e) => {
      state.wWater = Number(e.target.value);
      updateWaterOutput();
      scheduleSimulate();
    });

    const bindSlider = (id, outId, key) => {
      const el = $(id);
      el.addEventListener("input", () => {
        state[key] = Number(el.value);
        $(outId).textContent = `${state[key]}%`;
        scheduleSimulate();
      });
    };
    bindSlider("sl-profit", "out-profit", "wProfit");
    bindSlider("sl-nitrogen", "out-nitrogen", "wNitrogen");

    // Tarjetas de Régimen hídrico & Destino productivo
    const bindPills = (containerId, stateKey) => {
      const container = $(containerId);
      if (!container) return;
      container.querySelectorAll("button[data-value]").forEach((btn) => {
        btn.addEventListener("click", () => {
          state[stateKey] = btn.dataset.value;
          container.querySelectorAll("button[data-value]").forEach((b) => {
            const active = b === btn;
            b.classList.toggle("active", active);
            b.setAttribute("aria-pressed", active ? "true" : "false");
          });
          scheduleSimulate(40);
        });
      });
    };
    bindPills("pills-irrigation", "irrigationMode");
    bindPills("pills-market", "marketGoal");
    bindPills("pills-fertilizer", "fertilizerType");
    bindPills("pills-tillage", "tillageMode");

    // Selección múltiple de problemas (mínimo 1 activo)
    const concernBox = $("pills-concern");
    if (concernBox) {
      let minNoteTimer = null;
      concernBox.querySelectorAll("button[data-value]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const val = btn.dataset.value;
          const idx = state.mainConcerns.indexOf(val);
          if (idx >= 0) {
            if (state.mainConcerns.length <= 1) {
              const note = $("concern-min-note");
              if (note) {
                note.classList.remove("hidden");
                clearTimeout(minNoteTimer);
                minNoteTimer = setTimeout(() => note.classList.add("hidden"), 2200);
              }
              return;
            }
            state.mainConcerns.splice(idx, 1);
            btn.classList.remove("active");
            btn.setAttribute("aria-pressed", "false");
          } else {
            state.mainConcerns.push(val);
            btn.classList.add("active");
            btn.setAttribute("aria-pressed", "true");
          }
          const note = $("concern-min-note");
          if (note) note.classList.add("hidden");
          scheduleSimulate(40);
        });
      });
    }

    // Clima: Lluvia y Sequía
    $("sl-rain").addEventListener("input", (e) => {
      setRain(Number(e.target.value));
    });
    $("btn-drought").addEventListener("click", () => {
      setRain(state.rainPct === 20 ? 0 : 20);
    });

    // Clima: Ola de Calor (+0.0 a +3.0 °C)
    $("sl-temp").addEventListener("input", (e) => {
      setTemp(Number(e.target.value) / 10);
    });
    $("btn-heat").addEventListener("click", () => {
      setTemp(Math.abs(state.tempIncreaseC - 2.0) < 0.05 ? 0.0 : 2.0);
    });

    // Superficie (hectáreas)
    $("input-ha").addEventListener("input", (e) => {
      let v = Number(e.target.value);
      if (v > MAX_HA) {
        v = MAX_HA;
        e.target.value = MAX_HA;
        state.cappedWarning = true;
        $("poly-info").classList.remove("hidden");
        $("poly-info").textContent = `Aviso: Superficie limitada al máximo permitido de ${NUM.format(MAX_HA)} ha.`;
      } else {
        state.cappedWarning = false;
        if (!state.fromPolygon) $("poly-info").classList.add("hidden");
      }
      if (v > 0) {
        state.hectares = v;
        const s = state.suelos[state.locationId];
        if (s && $("header-parcel-label")) {
          $("header-parcel-label").textContent = `${s.zona_label} · ${NUM.format(state.hectares)} ha`;
        }
        updateWaterOutput();
        scheduleSimulate();
      }
    });
    $("input-ha").addEventListener("blur", (e) => {
      if (!(Number(e.target.value) > 0)) e.target.value = state.hectares;
    });

    // Cultivo actual / que necesita sembrar
    $("select-crop").addEventListener("change", (e) => {
      state.currentCrop = e.target.value;
      const isCustom = state.currentCrop === "__otro__";
      const customBox = $("custom-crop-box");
      if (customBox) customBox.classList.toggle("hidden", !isCustom);
      if (isCustom) {
        const inp = $("input-custom-crop");
        if (inp) inp.focus();
      }
      scheduleSimulate(20);
    });

    const customCropInp = $("input-custom-crop");
    const customCropTierSel = $("select-custom-crop-tier");
    if (customCropInp) {
      customCropInp.addEventListener("input", (e) => {
        state.customCropName = e.target.value;
        const detectedTier = inferCustomCropWaterTier(e.target.value);
        if (detectedTier) {
          state.customCropWaterTier = detectedTier;
          if (customCropTierSel) customCropTierSel.value = detectedTier;
        }
        scheduleSimulate(150);
      });
    }
    if (customCropTierSel) {
      customCropTierSel.addEventListener("change", (e) => {
        state.customCropWaterTier = e.target.value;
        scheduleSimulate(20);
      });
    }

    // Edición y restauración manual de datos de suelo (Paso 2)
    $("btn-edit-soil").addEventListener("click", () => {
      state.editingSoil = !state.editingSoil;
      renderSoil();
    });
    $("btn-reset-soil").addEventListener("click", () => {
      state.soilOverride = null;
      state.editingSoil = false;
      renderSoil();
      updateMapMarker(false);
      scheduleSimulate(20);
    });

    // Selector de modo de gráfica NASA (12 meses vs 10 años)
    const chartModeBox = $("chart-mode");
    if (chartModeBox) {
      chartModeBox.querySelectorAll("button[data-mode]").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.chartMode = btn.dataset.mode;
          chartModeBox.querySelectorAll("button[data-mode]").forEach((b) => {
            b.classList.toggle("active", b === btn);
          });
          renderChart();
        });
      });
    }

    // Modal Fusión de Datos NASA
    const modal = $("modal-fusion");
    $("btn-fusion").addEventListener("click", () => {
      modal.classList.remove("hidden");
      icons();
    });
    $("btn-close-fusion").addEventListener("click", () => {
      modal.classList.add("hidden");
    });
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.add("hidden");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modal.classList.contains("hidden")) {
        modal.classList.add("hidden");
      }
    });

    // Exportar Plan para Campo (Impresión limpia)
    $("btn-export").addEventListener("click", () => {
      renderPrintSheet();
      window.print();
    });
  }

  function setRain(pct) {
    state.rainPct = pct;
    $("sl-rain").value = pct;
    $("out-rain").textContent = pct === 0 ? "0%" : `-${pct}%`;
    $("btn-drought").setAttribute("aria-pressed", pct === 20 ? "true" : "false");
    renderChart();
    scheduleSimulate();
  }

  function setTemp(tempC) {
    const rounded = Math.round(tempC * 10) / 10;
    state.tempIncreaseC = rounded;
    $("sl-temp").value = Math.round(rounded * 10);
    $("out-temp").textContent = `+${rounded.toFixed(1)} °C`;
    $("btn-heat").setAttribute("aria-pressed", Math.abs(rounded - 2.0) < 0.05 ? "true" : "false");
    scheduleSimulate();
  }

  /* ---------- Simulation ---------- */
  function scheduleSimulate(delay = 100) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(simulate, delay);
  }

  async function simulate() {
    const seq = ++reqSeq;
    $("loading").classList.remove("hidden");
    try {
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          location_id: state.locationId,
          hectares: state.hectares,
          weight_water: state.wWater / 100,
          weight_profit: state.wProfit / 100,
          weight_nitrogen: state.wNitrogen / 100,
          rain_reduction_pct: state.rainPct / 100,
          temp_increase_c: state.tempIncreaseC,
          irrigation_mode: state.irrigationMode,
          market_goal: state.marketGoal,
          current_crop: state.currentCrop,
          custom_crop_name: state.currentCrop === "__otro__" ? state.customCropName.trim() : null,
          custom_crop_water_tier: state.customCropWaterTier,
          soil_override: state.soilOverride,
          fertilizer_type: state.fertilizerType,
          tillage_mode: state.tillageMode,
          main_concern: state.mainConcerns,
          selected_problems: state.mainConcerns,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (seq !== reqSeq) return;
      state.lastSimResult = data;
      if (data.parcel_context && data.parcel_context.problema_principal && $("soil-problem")) {
        const prefix = data.is_custom_soil ? "Diagnóstico en campo (personalizado): " : "Diagnóstico local: ";
        $("soil-problem").textContent = `${prefix}${data.parcel_context.problema_principal}`;
      }
      renderBaseline(data);
      renderSolutions(data);
      renderPrintSheet();
    } catch (err) {
      console.error(err);
      $("baseline-card").innerHTML = `<div class="card text-sm text-red-700">No se pudo calcular el diagnóstico.</div>`;
      $("plans").innerHTML = `<div class="card text-sm text-red-700">No se pudo calcular la simulación.</div>`;
    } finally {
      if (seq === reqSeq) $("loading").classList.add("hidden");
    }
  }

  function formatEvidenceText(text) {
    return String(text).replace(/(?<![\d,.])(\d{4,})(\.\d+)?(?=\s*(?:ha|mm)\b)/g, (_m, int, dec) =>
      Number(int).toLocaleString("en-US") + (dec || "")
    );
  }

  function trafficBox(kind, level) {
    return `
      <div class="traffic-box traffic-${level}">
        <div class="t-lbl">${kind}</div>
        <div class="t-val">${LIGHT_LABELS[level] || level}</div>
      </div>`;
  }

  /* ---------- Step 4: Diagnóstico de tu Plan Actual (Línea Base) ---------- */
  function renderBaseline(data) {
    const ctx = data.parcel_context;
    const tempText = state.tempIncreaseC > 0 ? ` · Ola de calor +${state.tempIncreaseC.toFixed(1)} °C` : "";
    $("rain-note").textContent =
      `Lluvia anual: ${ctx.annual_simulated_rain_mm.toFixed(1)} mm` +
      (state.rainPct > 0 ? ` (histórica ${ctx.annual_historical_rain_mm.toFixed(1)} mm)` : " (promedio histórico)") +
      tempText;

    const basePlan = data.plans.find((p) => p.plan_id === "plan_actual") || data.plans[0];
    if (!basePlan) return;

    const bal = basePlan.balance_nitrogeno_y_cobertura || {};
    const rows = basePlan.years
      .map(
        (y) =>
          `<tr><td class="font-bold">Año ${y.year}</td><td>${y.pv_crop_label}</td><td>${y.oi_crop_label}</td></tr>`
      )
      .join("");

    const validationNotes = (basePlan.local_validation_notes || [])
      .map((note) => `<li>${note}</li>`)
      .join("");

    const regimeShort = state.irrigationMode === "riego" ? "Riego de Auxilio" : "Solo Temporal";

    $("baseline-card").innerHTML = `
      <article class="card plan-card border-amber-300 bg-amber-50/20">
        <div class="flex items-start justify-between gap-2">
          <div>
            <span class="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900">
              Línea Base · Sin Rotación
            </span>
            <h3 class="plan-name mt-1.5">${basePlan.plan_name}</h3>
            <p class="plan-focus">${NUM.format(state.hectares)} ha en ${data.zona_label} · ${regimeShort}</p>
          </div>
          <div class="text-right">
            <div class="score-big text-amber-800">${Math.round(basePlan.suitability_score)}%</div>
            <div class="score-sub">viabilidad</div>
          </div>
        </div>

        <div>
          <div class="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">Semáforos de Riesgo a 3 Años</div>
          <div class="traffic-grid">
            ${trafficBox("Sequía", basePlan.semaforo_sequia)}
            ${trafficBox("Heladas", basePlan.semaforo_heladas)}
            ${trafficBox("Plagas", basePlan.semaforo_plagas)}
          </div>
        </div>

        <div class="grid grid-cols-1 gap-2">
          <div class="stat-box bg-white">
            <div class="lbl">CONSUMO HÍDRICO TOTAL (LÍNEA BASE 3 AÑOS)</div>
            <div class="val text-[#0284C7] text-lg">${NUM.format(Math.round(basePlan.consumo_agua_litros || 0))} L</div>
            <div class="text-[11px] text-slate-500 mt-0.5">Equivalente a ${NUM.format(
      Math.round(basePlan.consumo_agua_total_3a_m3 || 0)
    )} m³ (${NUM.format(Math.round(basePlan.demanda_agua_efectiva_3a_mm || 0))} mm)</div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="stat-box bg-white">
              <div class="lbl">Utilidad Neta (3 años)</div>
              <div class="val text-slate-900">${CURRENCY.format(basePlan.ingreso_neto_total_mxn)}</div>
              <div class="text-[11px] text-slate-500 mt-0.5">${CURRENCY.format(basePlan.ingreso_neto_ha_3a_mxn)} / ha</div>
            </div>
            <div class="stat-box bg-white">
              <div class="lbl">Cobertura del Suelo</div>
              <div class="val text-slate-900">${bal.meses_suelo_protegido_3a}/36 meses</div>
              <div class="text-[11px] text-rose-700 font-medium mt-0.5">${bal.meses_suelo_desnudo_3a} meses suelo desnudo</div>
            </div>
          </div>
        </div>

        <div>
          <div class="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">Calendario Actual (3 Años)</div>
          <div class="table-scroll">
            <table class="mini-table">
              <thead><tr><th>Ciclo</th><th>Primavera-Verano</th><th>Otoño-Invierno</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </div>

        <p class="nasa-note">${formatEvidenceText(basePlan.nasa_evidence_summary)}</p>

        <details class="validation">
          <summary>
            <span>¿Qué no ve el satélite? (Validación local requerida)</span>
          </summary>
          <ul>${validationNotes}</ul>
        </details>
      </article>
    `;
    icons();
  }

  /* ---------- Step 5: Tus Opciones de Rotación (De lo Bueno a lo Óptimo) ---------- */
  function renderSolutions(data) {
    const basePlan = data.plans.find((p) => p.plan_id === "plan_actual") || data.plans[0];
    const alternatives = data.plans.filter((p) => p.plan_id !== "plan_actual");

    // Ordenar de menor a mayor suitability_score: primero la Primera Alternativa (buena), debajo la Mejor Opción (óptima)
    const sorted = [...alternatives].sort((a, b) => a.suitability_score - b.suitability_score);

    $("plans").innerHTML = sorted
      .map((p, idx) => {
        const isOptimal = idx === sorted.length - 1;
        const bal = p.balance_nitrogeno_y_cobertura || {};
        const extraMoney = p.ingreso_neto_total_mxn - (basePlan ? basePlan.ingreso_neto_total_mxn : 0);
        const extraMoneyStr =
          extraMoney >= 0
            ? `+${CURRENCY.format(extraMoney)} extra vs. tu plan actual`
            : `${CURRENCY.format(extraMoney)} vs. tu plan actual`;

        const rows = p.years
          .map(
            (y) =>
              `<tr><td class="font-bold">Año ${y.year}</td><td>${y.pv_crop_label}</td><td>${y.oi_crop_label}</td></tr>`
          )
          .join("");

        const validationNotes = (p.local_validation_notes || [])
          .map((note) => `<li>${note}</li>`)
          .join("");

        return `
        <article class="card plan-card ${isOptimal ? "best" : ""}">
          ${isOptimal
            ? `<div class="best-tag"><i data-lucide="award" class="w-3.5 h-3.5"></i> MEJOR OPCIÓN PARA TU PARCELA</div>`
            : `<div class="alt-tag"><i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i> PRIMERA ALTERNATIVA · BUENA OPCIÓN</div>`
          }

          <div class="flex items-start justify-between gap-2">
            <div>
              <h3 class="plan-name">${p.plan_name}</h3>
              <p class="plan-focus">${p.strategy_focus}</p>
            </div>
            <div class="text-right shrink-0">
              <div class="score-big">${Math.round(p.suitability_score)}%</div>
              <div class="score-sub">afinidad</div>
            </div>
          </div>

          <!-- Beneficio directo frente al Plan Actual -->
          <div class="grid grid-cols-1 gap-2">
            <div class="stat-box ${isOptimal ? "bg-emerald-50/80 border-emerald-300" : "bg-slate-50"}">
              <div class="lbl">Utilidad Neta Estimada (3 años)</div>
              <div class="val text-[#0F5132] text-lg">${CURRENCY.format(p.ingreso_neto_total_mxn)}</div>
              <div class="text-xs font-bold text-emerald-700 mt-0.5">${extraMoneyStr}</div>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div class="stat-box bg-white">
                <div class="lbl">AGUA AHORRADA</div>
                <div class="val text-[#0284C7]">${NUM.format(Math.round(p.ahorro_agua_litros || 0))} L</div>
                <div class="text-[11px] text-slate-500 mt-0.5">${NUM.format(
            Math.round(p.ahorro_agua_m3 || 0)
          )} m³ menos que no rotar</div>
              </div>
              <div class="stat-box bg-white">
                <div class="lbl">Salud del Suelo</div>
                <div class="val text-slate-900">${bal.ciclos_fijacion_nitrogeno_3a} ciclos N</div>
                <div class="text-[11px] text-emerald-700 font-semibold mt-0.5">${bal.meses_suelo_protegido_3a
          }/36 meses cubierto</div>
              </div>
            </div>
          </div>

          <div>
            <div class="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">Rotación Paso a Paso (3 Años)</div>
            <div class="table-scroll">
              <table class="mini-table">
                <thead><tr><th>Año</th><th>Primavera-Verano</th><th>Otoño-Invierno</th></tr></thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
          </div>

          <div class="traffic-grid">
            ${trafficBox("Sequía", p.semaforo_sequia)}
            ${trafficBox("Heladas", p.semaforo_heladas)}
            ${trafficBox("Plagas", p.semaforo_plagas)}
          </div>

          <p class="nasa-note">${formatEvidenceText(p.nasa_evidence_summary)}</p>

          <details class="validation" open>
            <summary>
              <span>Incertidumbres y Validación Local (¿Qué no ve el satélite?)</span>
            </summary>
            <ul>${validationNotes}</ul>
          </details>
        </article>`;
      })
      .join("");
    icons();
  }

  /* ---------- Print Sheet (Exportar Plan para Campo) ---------- */
  function renderPrintSheet() {
    const container = $("print-sheet");
    if (!container || !state.lastSimResult) return;
    const data = state.lastSimResult;
    const ctx = data.parcel_context;
    const recPlan = data.plans.find((p) => p.plan_id === data.recommended_plan_id) || data.plans[0];
    if (!recPlan) return;

    const regimeLabel =
      state.irrigationMode === "riego" ? "Riego de Auxilio (pozo / cintilla)" : "Solo Temporal (dependiente de lluvia)";
    const marketLabel =
      state.marketGoal === "forraje" ? "Forraje Ganadero (establo / paca)" : "Venta de Grano (comercialización)";
    const dateStr = new Date().toLocaleDateString("es-MX", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });

    const rotRows = recPlan.years
      .map(
        (y) => `
        <tr>
          <td><b>Año ${y.year}</b></td>
          <td>${y.pv_crop_label}</td>
          <td>${y.oi_crop_label}</td>
          <td>${NUM.format(Math.round(y.effective_water_demand_mm))} mm</td>
          <td>${CURRENCY.format(y.adjusted_net_income_ha_mxn)} / ha</td>
        </tr>`
      )
      .join("");

    const summaryRows = data.plans
      .map((p) => {
        const isRec = p.plan_id === data.recommended_plan_id;
        const waterStr =
          p.plan_id === "plan_actual"
            ? `Consumo base: ${NUM.format(Math.round(p.consumo_agua_litros || 0))} L`
            : `Ahorro: ${NUM.format(Math.round(p.ahorro_agua_litros || 0))} L`;
        const bal = p.balance_nitrogeno_y_cobertura || {};
        return `
        <tr>
          <td><b>${p.plan_name}</b> ${isRec ? "(Mejor Opción)" : ""}</td>
          <td>${CURRENCY.format(p.ingreso_neto_total_mxn)}</td>
          <td>${waterStr}</td>
          <td>${bal.ciclos_fijacion_nitrogeno_3a} ciclos N · ${bal.meses_suelo_protegido_3a}/36 meses cubierto</td>
          <td>Sequía: ${LIGHT_LABELS[p.semaforo_sequia]} · Heladas: ${LIGHT_LABELS[p.semaforo_heladas]
          } · Plagas: ${LIGHT_LABELS[p.semaforo_plagas]}</td>
        </tr>`;
      })
      .join("");

    const checklistItems = (recPlan.local_validation_notes || [])
      .map((note) => `<li><span class="ps-box"></span><span>${note}</span></li>`)
      .join("");

    container.innerHTML = `
      <div style="border-bottom:2px solid #0f5132; padding-bottom:8pt; margin-bottom:10pt; display:flex; justify-content:space-between; align-items:flex-end;">
        <div>
          <div class="ps-title">AgroShift — Hoja de Ruta para Campo (3 Años)</div>
          <div class="ps-sub">Fusión de Telemetría NASA (MODIS MOD13Q1 + GPM IMERG + MERRA-2) y Diagnóstico Edáfico Local</div>
        </div>
        <div class="ps-sub" style="text-align:right;">
          <div><b>Fecha:</b> ${dateStr}</div>
          <div><b>Parcela:</b> ${data.zona_label} (${data.municipio})</div>
        </div>
      </div>

      <div class="ps-h">1. Perfil de Parcela y Escenario Simulado</div>
      <div class="ps-grid">
        <div><b>Superficie Analizada:</b> ${NUM.format(state.hectares)} ha</div>
        <div><b>Cultivo Actual / Base (Año 1):</b> ${data.current_crop_label || state.currentCrop} (${data.current_crop_cycle_label || ""
      })</div>
        <div><b>Tipo de Suelo y Textura:</b> ${ctx.tipo_suelo_label} (${ctx.textura_label}) · MO ${ctx.materia_organica_pct
      }% · Elevación ${NUM.format(ctx.local_elevation_m)} msnm · Pendiente ${ctx.pendiente_pct ?? state.suelos[state.locationId]?.pendiente_pct ?? 2.0
      }% ${data.is_custom_soil || ctx.is_custom_soil
        ? "<b>(Datos de suelo calibrados por el agricultor)</b>"
        : "(Perfil regional)"
      }</div>
        <div><b>Régimen Hídrico:</b> ${regimeLabel}</div>
        <div><b>Destino Productivo:</b> ${marketLabel}</div>
        <div><b>Fertilización Actual:</b> ${data.fertilizer_label || ctx.fertilizer_label || state.fertilizerType}</div>
        <div><b>Manejo de Rastrojo:</b> ${data.tillage_label || ctx.tillage_label || state.tillageMode}</div>
        <div><b>Preocupación Principal:</b> ${data.main_concern_label || ctx.main_concern_label || state.mainConcerns.join(", ")}</div>
        <div><b>Escenario Climático:</b> Lluvia ${state.rainPct === 0 ? "histórica normal" : `-${state.rainPct}%`
      } (${ctx.annual_simulated_rain_mm.toFixed(1)} mm/año) · Temperatura +${state.tempIncreaseC.toFixed(1)} °C</div>
      </div>

      <div class="ps-h">2. Mejor Opción Recomendada: ${recPlan.plan_name} (Afinidad ${Math.round(
        recPlan.suitability_score
      )}%)</div>
      <p class="ps-sub" style="margin:0 0 6pt 0;">${formatEvidenceText(recPlan.nasa_evidence_summary)}</p>
      <table class="ps-table">
        <thead>
          <tr>
            <th>Ciclo Anual</th>
            <th>Primavera - Verano (PV)</th>
            <th>Otoño - Invierno (OI)</th>
            <th>Demanda Hídrica</th>
            <th>Ingreso Neto / ha</th>
          </tr>
        </thead>
        <tbody>${rotRows}</tbody>
      </table>

      <div class="ps-h">3. Comparativa de Planes a 3 Años (${NUM.format(state.hectares)} ha)</div>
      <table class="ps-table">
        <thead>
          <tr>
            <th>Plan de Transición</th>
            <th>Utilidad Neta Estimada (3 años)</th>
            <th>Balance Hídrico en Litros</th>
            <th>Regeneración de Suelo</th>
            <th>Semáforo de Riesgos</th>
          </tr>
        </thead>
        <tbody>${summaryRows}</tbody>
      </table>

      <div class="ps-h">4. Lista de Verificación en Campo (Validación Local Requerida)</div>
      <ul class="ps-check">${checklistItems}</ul>

      <div class="ps-disc">
        <b>Aviso de apoyo a la decisión:</b> Esta hoja de ruta integra series satelitales NASA (2016–2026) y parámetros agronómicos regionales de Coahuila. Complementa, pero nunca sustituye, el muestreo físico en parcela ni el criterio del agricultor y del ingeniero agrónomo local.
      </div>
    `;
  }

  /* ---------- Chart.js Dual (12 Meses Estacional vs. 10 Años 2016-2026) ---------- */
  const alertShadingPlugin = {
    id: "alertShading",
    beforeDatasetsDraw(ch, _args, opts) {
      const { ctx, chartArea, scales } = ch;
      if (!chartArea || !opts.alerts || !scales.x) return;
      const x = scales.x;
      const count = opts.alerts.length;
      if (!count) return;
      ctx.save();
      ctx.fillStyle = "rgba(244, 63, 94, 0.12)";
      const step = chartArea.width / count;
      opts.alerts.forEach((flag, i) => {
        if (!flag) return;
        const cx = x.getPixelForValue(i);
        const half = Math.max(step / 2, 2);
        const left = Math.max(chartArea.left, cx - half);
        const right = Math.min(chartArea.right, cx + half);
        ctx.fillRect(left, chartArea.top, right - left, chartArea.bottom - chartArea.top);
      });
      ctx.restore();
    },
  };

  function renderChartSubtitle(locName, isHistory) {
    const gpmTip = tipBadge(
      "GPM/IMERG: misión satelital de la NASA y JAXA que mide la lluvia cada 30 minutos con resolución de 10 km."
    );
    const ndviTip = tipBadge(
      "MODIS NDVI: Índice de verdor vegetal (0 a 1) a 250 m por píxel. Valores menores a 0.34 indican suelo seco o descubierto.",
      true
    );
    if (isHistory) {
      $("chart-subtitle").innerHTML =
        `${locName} — Serie observada (2016–2026, 130 meses): Lluvia GPM/IMERG ${gpmTip} vs. Verdor MODIS NDVI ${ndviTip}`;
    } else {
      $("chart-subtitle").innerHTML =
        `${locName} — Ciclo promedio (12 meses): Lluvia GPM/IMERG ${gpmTip} vs. Verdor MODIS NDVI ${ndviTip}`;
    }
  }

  function updateContextBarSeasonal(months, rain, ndvi, alerts) {
    const bar = $("nasa-context-bar");
    if (!bar) return;

    const wetMonths = [];
    const criticalMonths = [];
    let maxRainIdx = 0;
    let maxNdviIdx = 0;

    months.forEach((m, i) => {
      const label = MONTHS[m.month - 1];
      if (alerts[i]) {
        criticalMonths.push(label);
      } else {
        wetMonths.push(label);
      }
      if (rain[i] > rain[maxRainIdx]) maxRainIdx = i;
      if (ndvi[i] > ndvi[maxNdviIdx]) maxNdviIdx = i;
    });

    const annualRain = rain.reduce((acc, v) => acc + v, 0);

    bar.innerHTML = `
      <div class="p-2.5 rounded-lg bg-rose-50/80 border border-rose-200 text-xs">
        <div class="font-bold text-rose-900 flex items-center gap-1.5 mb-0.5">
          <span class="w-2 h-2 rounded-full bg-rose-500"></span>
          Meses secos o con suelo desnudo (${criticalMonths.length} meses en rosa)
        </div>
        <div class="text-slate-600 leading-snug">
          En <strong>${criticalMonths.join(", ") || "ningún mes"
      }</strong> tu parcela recibe poca lluvia (<code>&lt; 20 mm</code>) o queda descubierta (<code>NDVI &lt; 0.34</code>). Lluvia anual: <strong>${annualRain.toFixed(
        1
      )} mm</strong>.
        </div>
      </div>
      <div class="p-2.5 rounded-lg bg-emerald-50/80 border border-emerald-200 text-xs">
        <div class="font-bold text-emerald-900 flex items-center gap-1.5 mb-0.5">
          <span class="w-2 h-2 rounded-full bg-emerald-600"></span>
          Meses de mayor humedad y verdor (${wetMonths.length} meses)
        </div>
        <div class="text-slate-600 leading-snug">
          Mejor humedad en <strong>${wetMonths.join(", ") || "Ninguno"}</strong>, con pico de lluvia en <strong>${MONTHS[maxRainIdx]
      } (${rain[maxRainIdx]} mm)</strong> y máximo verdor en <strong>${MONTHS[maxNdviIdx]} (NDVI ${ndvi[
        maxNdviIdx
      ].toFixed(2)})</strong>.
        </div>
      </div>
    `;
  }

  function updateContextBarHistory(series, alerts) {
    const bar = $("nasa-context-bar");
    if (!bar || !series.length) return;

    const totalMonths = series.length;
    const criticalCount = alerts.filter(Boolean).length;
    const avgRain = series.reduce((a, r) => a + r.lluvia_mm, 0) / totalMonths;
    const avgNdvi = series.reduce((a, r) => a + r.ndvi_mean, 0) / totalMonths;

    bar.innerHTML = `
      <div class="p-2.5 rounded-lg bg-rose-50/80 border border-rose-200 text-xs">
        <div class="font-bold text-rose-900 flex items-center gap-1.5 mb-0.5">
          <span class="w-2 h-2 rounded-full bg-rose-500"></span>
          Estrés recurrente en 10 años (${criticalCount} de ${totalMonths} meses)
        </div>
        <div class="text-slate-600 leading-snug">
          El <strong>${Math.round(
      (criticalCount / totalMonths) * 100
    )}%</strong> de los meses entre 2016 y 2026 tuvo baja lluvia o suelo descubierto, demostrando por qué el monocultivo agota tu tierra.
        </div>
      </div>
      <div class="p-2.5 rounded-lg bg-emerald-50/80 border border-emerald-200 text-xs">
        <div class="font-bold text-emerald-900 flex items-center gap-1.5 mb-0.5">
          <span class="w-2 h-2 rounded-full bg-emerald-600"></span>
          Promedio satelital 2016–2026
        </div>
        <div class="text-slate-600 leading-snug">
          Lluvia media de <strong>${avgRain.toFixed(1)} mm/mes</strong> y verdor medio <strong>NDVI ${avgNdvi.toFixed(
      3
    )}</strong>. Rotar con cobertura invernal conserva esa humedad en el suelo.
        </div>
      </div>
    `;
  }

  function renderChart() {
    const loc = state.climatology[state.locationId];
    const s = state.suelos[state.locationId];
    if (!loc) return;

    const isHistory = state.chartMode === "history";
    const locName = (s && (s.zona_label || s.display_name)) || state.locationId;
    renderChartSubtitle(locName, isHistory);

    let labels = [];
    let rain = [];
    let ndvi = [];
    let alerts = [];
    let rainLabel = "";

    if (isHistory) {
      const series = state.historyByLocation[state.locationId] || [];
      labels = series.map((r) => r.date_label);
      rain = series.map((r) => +r.lluvia_mm.toFixed(1));
      ndvi = series.map((r) => +r.ndvi_mean.toFixed(3));
      alerts = series.map((r) => r.ndvi_mean < 0.34 || r.lluvia_mm < 20);
      rainLabel = "Lluvia GPM/IMERG (mm)";
      updateContextBarHistory(series, alerts);
    } else {
      const factor = 1 - state.rainPct / 100;
      const months = loc.months;
      labels = months.map((m) => MONTHS[m.month - 1]);
      rain = months.map((m) => +((m.prectotcorr_mm_mean ?? m.lluvia_mm ?? 0) * factor).toFixed(1));
      ndvi = months.map((m) => +m.ndvi_mean.toFixed(3));
      alerts = months.map((m, i) => m.ndvi_mean < 0.34 || rain[i] < 20);
      rainLabel = state.rainPct > 0 ? `Lluvia GPM (-${state.rainPct}%)` : "Lluvia GPM/IMERG (mm)";
      updateContextBarSeasonal(months, rain, ndvi, alerts);
    }

    const data = {
      labels,
      datasets: [
        {
          type: "bar",
          label: rainLabel,
          data: rain,
          backgroundColor: "rgba(125, 211, 252, 0.6)",
          borderRadius: isHistory ? 1 : 4,
          yAxisID: "y",
          order: 2,
        },
        {
          type: "line",
          label: "Vigor vegetal MODIS NDVI",
          data: ndvi,
          borderColor: "#A3E635",
          backgroundColor: "#A3E635",
          tension: 0.35,
          pointRadius: isHistory ? 0 : 3,
          borderWidth: isHistory ? 2 : 3,
          yAxisID: "y1",
          order: 1,
        },
      ],
    };

    const options = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            usePointStyle: true,
            boxWidth: 8,
            color: "rgba(255,255,255,0.7)",
            font: { family: "Inter", size: 11 },
            generateLabels(chartInstance) {
              const base = Chart.defaults.plugins.legend.labels.generateLabels(chartInstance);
              base.push({
                text: "Meses críticos (sequía / suelo expuesto)",
                fillStyle: "rgba(252, 165, 165, 0.28)",
                strokeStyle: "rgba(225, 29, 72, 0.55)",
                lineWidth: 1,
                pointStyle: "rectRounded",
                hidden: false,
              });
              return base;
            },
          },
          onClick(e, legendItem, legend) {
            if (typeof legendItem.datasetIndex === "number") {
              Chart.defaults.plugins.legend.onClick.call(this, e, legendItem, legend);
            }
          },
        },
        alertShading: { alerts },
        tooltip: {
          backgroundColor: "rgba(20, 30, 14, 0.92)",
          titleColor: "#FFFFFF",
          bodyColor: "rgba(255,255,255,0.85)",
          borderColor: "rgba(255,255,255,0.25)",
          borderWidth: 1,
          callbacks: {
            afterBody: (items) => {
              const i = items[0].dataIndex;
              return alerts[i]
                ? "Mes crítico: baja lluvia (< 20 mm) o baja cobertura (NDVI < 0.34)"
                : "Mes con buena humedad y cobertura vegetal";
            },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: "Lluvia mensual (mm)", color: "rgba(255,255,255,0.7)", font: { size: 10 } },
          ticks: { color: "rgba(255,255,255,0.7)" },
          grid: { color: "rgba(255,255,255,0.14)" },
          border: { color: "rgba(255,255,255,0.22)" },
        },
        y1: {
          position: "right",
          min: 0.1,
          max: 0.7,
          title: { display: true, text: "Verdor vegetal (NDVI: 0 seco – 1 verde)", color: "rgba(255,255,255,0.7)", font: { size: 10 } },
          ticks: { color: "rgba(255,255,255,0.7)" },
          grid: { drawOnChartArea: false },
          border: { color: "rgba(255,255,255,0.22)" },
        },
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: isHistory ? 8 : 12,
            color: "rgba(255,255,255,0.7)",
            font: { size: 10 },
          },
        },
      },
    };

    if (chart) {
      chart.data = data;
      chart.options = options;
      chart.update();
    } else {
      chart = new Chart($("nasa-chart"), { data, options, plugins: [alertShadingPlugin] });
    }
  }

  /* ---------- PWA: Service Worker & Instalación Nativa ---------- */
  let deferredInstallPrompt = null;

  function setupPwaInstall() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/static/sw.js", { scope: "/" }).catch(() => {});
    }

    const installBtn = $("btn-install-app");
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredInstallPrompt = e;
      if (installBtn) installBtn.classList.remove("hidden");
    });

    window.addEventListener("appinstalled", () => {
      deferredInstallPrompt = null;
      if (installBtn) installBtn.classList.add("hidden");
    });

    if (installBtn) {
      installBtn.addEventListener("click", async () => {
        if (!deferredInstallPrompt) return;
        deferredInstallPrompt.prompt();
        try {
          await deferredInstallPrompt.userChoice;
        } finally {
          deferredInstallPrompt = null;
          installBtn.classList.add("hidden");
        }
      });
    }
  }

  /* ---------- Init ---------- */
  async function init() {
    setupPwaInstall();
    const res = await fetch("/api/init");
    const d = await res.json();
    state.suelos = Object.fromEntries(d.suelos.map((s) => [s.location_id, s]));
    state.cultivos = d.cultivos;
    state.climatology = d.climatology.locations || d.climatology;
    state.historyByLocation = d.history_by_location || {};
    state.hectares = DEFAULT_HA;
    $("input-ha").value = DEFAULT_HA;
    updateWaterOutput();

    renderTabs();
    renderCropSelector();
    renderSoil();
    initMap();
    bindControls();
    renderChart();
    goToStep(1);
    simulate();
  }

  document.addEventListener("DOMContentLoaded", init);
})();

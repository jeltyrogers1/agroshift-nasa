/* Kultiva — Mobile-First 6-Step Wizard Controller (Vanilla ES6 + Leaflet + Chart.js) */
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
    1: "Comenzar",
    2: "Siguiente",
    3: "Siguiente",
    4: "Calcular diagnóstico",
    5: "Ver rotaciones",
    6: "Exportar plan",
  };

  const state = {
    currentStep: 1,
    suelos: {},
    cultivos: [],
    familias: [],
    catalogoAgrupado: [],
    cropCategoryFilter: "all",
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
    currentCrop: "Maiz",
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
      if (!sec) continue;
      const isTarget = i === target;
      sec.classList.toggle("hidden", !isTarget);
      if (isTarget) {
        sec.classList.remove("step-enter");
        void sec.offsetWidth;
        sec.classList.add("step-enter");
        sec.onanimationend = (e) => {
          if (e.target === sec) sec.classList.remove("step-enter");
        };
      } else {
        sec.classList.remove("step-enter");
      }
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

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function buildCatalogGroupsFallback() {
    const byCat = new Map();
    for (const c of state.cultivos || []) {
      const catId = c.categoria_siap || "Otros";
      const famId = c.familia_cultivo || c.cultivo;
      if (!byCat.has(catId)) {
        byCat.set(catId, {
          categoria_siap: catId,
          categoria_label: catId.replace(/_/g, " "),
          familiasMap: new Map(),
        });
      }
      const catEntry = byCat.get(catId);
      if (!catEntry.familiasMap.has(famId)) {
        catEntry.familiasMap.set(famId, {
          familia_cultivo: famId,
          familia_label: famId.replace(/_/g, " "),
          variedades: [],
        });
      }
      catEntry.familiasMap.get(famId).variedades.push(c);
    }
    return Array.from(byCat.values()).map((cat) => ({
      categoria_siap: cat.categoria_siap,
      categoria_label: cat.categoria_label,
      familias: Array.from(cat.familiasMap.values()).map((fam) => ({
        ...fam,
        variedades_count: fam.variedades.length,
      })),
    }));
  }

  function renderCropSelector() {
    const sel = $("select-crop");
    if (!sel) return;

    const groups =
      Array.isArray(state.catalogoAgrupado) && state.catalogoAgrupado.length
        ? state.catalogoAgrupado
        : buildCatalogGroupsFallback();
    if (!groups.length) return;

    const catFilter = state.cropCategoryFilter || "all";
    const visibleCategories = catFilter === "all" ? groups : groups.filter((g) => g.categoria_siap === catFilter);

    const optgroupsHtml = visibleCategories
      .map((cat) =>
        (cat.familias || [])
          .map((fam) => {
            const count = fam.variedades_count || (fam.variedades || []).length;
            const autoOpt = `<option value="${escapeHtml(fam.familia_cultivo)}">★ ${escapeHtml(
              fam.familia_label
            )} (Auto-selección por zona)</option>`;
            const varietyOpts = (fam.variedades || [])
              .map(
                (v) =>
                  `<option value="${escapeHtml(v.cultivo)}">${escapeHtml(v.cultivo_label)} · ${Math.round(
                    Number(v.consumo_agua_mm || 0)
                  )} mm</option>`
              )
              .join("");
            return `<optgroup label="${escapeHtml(cat.categoria_label)} · ${escapeHtml(
              fam.familia_label
            )} (${count})">${autoOpt}${varietyOpts}</optgroup>`;
          })
          .join("")
      )
      .join("");

    sel.innerHTML = optgroupsHtml + `<option value="__otro__">Otro cultivo... (Escribir manualmente)</option>`;

    // Mantener selección actual si existe en las opciones visibles; si no, elegir la primera familia visible
    const hasCurrent = Array.from(sel.options).some((opt) => opt.value === state.currentCrop);
    if (hasCurrent) {
      sel.value = state.currentCrop;
    } else if (sel.options.length > 0) {
      sel.value = sel.options[0].value;
      state.currentCrop = sel.value;
    }

    const customBox = $("custom-crop-box");
    if (customBox) customBox.classList.toggle("hidden", state.currentCrop !== "__otro__");
    updateResolvedCropHint(state.lastSimResult);
  }

  function updateResolvedCropHint(data) {
    const hint = $("crop-resolved-hint");
    if (!hint) return;
    if (state.currentCrop === "__otro__" || !data || !data.nombre_comun) {
      hint.classList.add("hidden");
      hint.textContent = "";
      return;
    }
    const modeTag =
      data.selection_mode === "variedad_oficial"
        ? "Variedad oficial"
        : `Auto-selección (${data.zona_label || data.municipio})`;
    const waterTxt = data.consumo_agua_mm ? ` · ${Math.round(Number(data.consumo_agua_mm))} mm` : "";
    const madurezTxt = data.dias_madurez ? ` · ${data.dias_madurez}` : "";
    hint.textContent = `${modeTag}: ${data.nombre_comun}${waterTxt}${madurezTxt}`;
    hint.classList.remove("hidden");
  }

  function renderOfficialVarietyMetaBlock(data) {
    if (!data || !data.nombre_comun) return "";
    const catLabel = String(data.categoria_siap || "").replace(/_/g, " ");
    const famLabel = String(data.familia_cultivo || "").replace(/_/g, " ");
    const clasif = String(data.clasificacion_oficial || "").replace(/_/g, " ");
    const waterMm = data.consumo_agua_mm ? `${Math.round(Number(data.consumo_agua_mm))} mm` : "N/D";
    const diasMad = data.dias_madurez || "N/D";
    const fuente = data.fuente_oficial || "Catálogo oficial Kultiva Coahuila";

    return `
      <div class="p-3 rounded-xl border border-white/10 bg-white/[0.03] text-xs space-y-1.5">
        <div class="text-[10px] font-bold uppercase tracking-wider text-[#a3e635]">Variedad oficial resuelta</div>
        <div class="font-semibold text-white leading-snug">${escapeHtml(data.nombre_comun)}</div>
        <div class="text-[11px] text-slate-300 leading-snug">
          <span>${escapeHtml(catLabel)} · ${escapeHtml(famLabel)}</span>
          ${clasif ? ` · <span class="opacity-80">${escapeHtml(clasif)}</span>` : ""}
        </div>
        <div class="text-[11px] text-slate-300 leading-snug">
          Lámina oficial: <strong class="text-white">${escapeHtml(waterMm)}</strong> · Madurez: <strong class="text-white">${escapeHtml(
      diasMad
    )}</strong>
        </div>
        <div class="text-[11px] text-slate-400 leading-snug">
          <strong class="text-slate-300">Fuente oficial:</strong> ${escapeHtml(fuente)}
        </div>
      </div>
    `;
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
            <span>Estrés térmico</span>
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
          <span>Imagen de alta resolución para trazar tus bordes.</span>
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

    // Filtro rápido por categoría SIAP (5 categorías)
    const catFilterBox = $("crop-category-filter");
    if (catFilterBox) {
      catFilterBox.querySelectorAll("button[data-cat]").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.cropCategoryFilter = btn.dataset.cat || "all";
          catFilterBox.querySelectorAll("button[data-cat]").forEach((b) => {
            const active = b === btn;
            b.classList.toggle("active", active);
            b.setAttribute("aria-pressed", active ? "true" : "false");
          });
          const prevCrop = state.currentCrop;
          renderCropSelector();
          if (state.currentCrop !== prevCrop) {
            scheduleSimulate(20);
          }
        });
      });
    }

    // Cultivo actual / que necesita sembrar
    $("select-crop").addEventListener("change", (e) => {
      state.currentCrop = e.target.value;
      const isCustom = state.currentCrop === "__otro__";
      const customBox = $("custom-crop-box");
      if (customBox) customBox.classList.toggle("hidden", !isCustom);
      if (isCustom) {
        updateResolvedCropHint(null);
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

    // Exportar Plan para Campo (Impresión limpia Top 5)
    $("btn-export").addEventListener("click", () => {
      renderPrintSheet();
      window.print();
    });

    // Descargar Excel completo con evaluación de los 168 cultivos oficiales
    $("btn-export-excel").addEventListener("click", exportExcel168);
  }

  function buildSimPayload() {
    return {
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
    };
  }

  function triggerBlobDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  async function exportExcel168() {
    const btn = $("btn-export-excel");
    const statusEl = $("export-excel-status");
    const payload = buildSimPayload();
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Generando análisis de 168 cultivos...</span>`;
    icons();
    if (statusEl) {
      statusEl.textContent = "Calculando el escenario para las 168 variedades oficiales en tu parcela...";
      statusEl.classList.remove("hidden");
    }

    try {
      const res = await fetch("/api/export-excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      if (!res.ok || (!ct.includes("spreadsheetml") && !ct.includes("octet-stream") && !ct.includes("text/csv"))) {
        throw new Error(`Exportación HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const disp = res.headers.get("content-disposition") || "";
      const match = disp.match(/filename="?([^";\n]+)"?/i);
      const fallbackName = ct.includes("text/csv")
        ? "Kultiva_Simulacion_168_Cultivos_Coahuila.csv"
        : "Kultiva_Simulacion_168_Cultivos_Coahuila.xlsx";
      triggerBlobDownload(blob, match ? match[1] : fallbackName);
      if (statusEl) {
        statusEl.textContent = "Archivo descargado: Top 5 de rotaciones + simulación completa de los 168 cultivos.";
      }
    } catch (err) {
      if (window.KultivaOffline && typeof window.KultivaOffline.generate168Csv === "function") {
        const csvContent = window.KultivaOffline.generate168Csv(payload);
        const csvBlob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        triggerBlobDownload(csvBlob, "Kultiva_Simulacion_168_Cultivos_Coahuila_Offline.csv");
        if (statusEl) {
          statusEl.textContent = "Modo sin conexión: se descargó la tabla completa de 168 cultivos en CSV compatible con Excel.";
        }
      } else {
        console.error(err);
        if (statusEl) {
          statusEl.textContent = "No se pudo descargar el archivo de Excel. Verifica tu conexión e intenta de nuevo.";
        }
      }
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="file-spreadsheet" class="w-4 h-4"></i><span>Descargar Excel completo (168 cultivos)</span>`;
      icons();
    }
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

  function applySimulationResult(data) {
    state.lastSimResult = data;
    updateResolvedCropHint(data);
    if (data.parcel_context && data.parcel_context.problema_principal && $("soil-problem")) {
      const prefix = data.is_custom_soil ? "Diagnóstico en campo (personalizado): " : "Diagnóstico local: ";
      $("soil-problem").textContent = `${prefix}${data.parcel_context.problema_principal}`;
    }
    renderBaseline(data);
    renderSolutions(data);
    renderPrintSheet();
  }

  async function simulate() {
    const seq = ++reqSeq;
    $("loading").classList.remove("hidden");
    const payload = buildSimPayload();
    try {
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (seq !== reqSeq) return;
      applySimulationResult(data);
    } catch (err) {
      if (window.KultivaOffline && typeof window.KultivaOffline.simulateScenarios === "function") {
        try {
          const offlineData = window.KultivaOffline.simulateScenarios(payload);
          if (seq !== reqSeq) return;
          applySimulationResult(offlineData);
          return;
        } catch (offErr) {
          console.error(offErr);
        }
      }
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

  const kpiRafIds = new WeakMap();

  function animateKPIs(container, duration = 550) {
    if (!container) return;
    const prevId = kpiRafIds.get(container);
    if (prevId) cancelAnimationFrame(prevId);

    const nodes = Array.from(container.querySelectorAll("[data-kpi-target]"));
    if (!nodes.length) return;

    const prefersReduced =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const fmtCache = new Map();
    const getFmt = (kind, decimals) => {
      if (kind === "currency") return CURRENCY;
      if (decimals === 0) return NUM;
      if (decimals === 1) return DEC1;
      const key = `n_${decimals}`;
      if (!fmtCache.has(key)) {
        fmtCache.set(
          key,
          new Intl.NumberFormat("es-MX", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          })
        );
      }
      return fmtCache.get(key);
    };

    const items = nodes.map((el) => {
      const target = Number(el.dataset.kpiTarget);
      const kind = el.dataset.kpiKind || "num";
      const suffix = el.dataset.kpiSuffix || "";
      const decimals = Number(el.dataset.kpiDecimals || 0);
      const fmt = getFmt(kind, decimals);
      const factor = Math.pow(10, decimals);
      return {
        el,
        target: Number.isFinite(target) ? target : 0,
        decimals,
        factor,
        fmt,
        suffix,
      };
    });

    const formatItem = (item, val) => {
      const rounded = item.decimals > 0 ? Math.round(val * item.factor) / item.factor || 0 : Math.round(val) || 0;
      return item.fmt.format(rounded) + item.suffix;
    };

    if (prefersReduced) {
      for (let i = 0; i < items.length; i++) {
        items[i].el.textContent = formatItem(items[i], items[i].target);
      }
      return;
    }

    for (let i = 0; i < items.length; i++) {
      items[i].el.textContent = formatItem(items[i], 0);
    }

    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const inv = 1 - progress;
      const eased = 1 - inv * inv * inv;

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        const current = progress >= 1 ? item.target : item.target * eased;
        item.el.textContent = formatItem(item, current);
      }

      if (progress < 1) {
        kpiRafIds.set(container, requestAnimationFrame(tick));
      } else {
        kpiRafIds.delete(container);
      }
    };

    kpiRafIds.set(container, requestAnimationFrame(tick));
  }

  function getHectareDisplay() {
    const haStr = String(state.hectares);
    const decimals = haStr.includes(".") ? Math.min(2, haStr.split(".")[1].length) : 0;
    const text =
      decimals === 0
        ? NUM.format(state.hectares)
        : decimals === 1
        ? DEC1.format(state.hectares)
        : new Intl.NumberFormat("es-MX", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(
            state.hectares
          );
    return { val: state.hectares, decimals, text: `${text} ha` };
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
    const haInfo = getHectareDisplay();
    const waterM3 = Math.round(basePlan.consumo_agua_total_3a_m3 || 0);
    const netMxn = Math.round(basePlan.ingreso_neto_total_mxn || 0);

    const baselineEl = $("baseline-card");
    baselineEl.innerHTML = `
      <article class="card plan-card result-enter" style="animation-delay: 0ms">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <span class="alt-tag">Línea base · sin rotación</span>
            <h3 class="plan-name mt-3">${basePlan.plan_name}</h3>
            <p class="plan-focus"><span data-kpi-target="${haInfo.val}" data-kpi-kind="num" data-kpi-decimals="${haInfo.decimals}" data-kpi-suffix=" ha">${haInfo.text}</span> · ${data.zona_label} · ${regimeShort}</p>
          </div>
          <div class="text-right shrink-0">
            <div class="score-big">${Math.round(basePlan.suitability_score)}%</div>
            <div class="score-sub">viabilidad</div>
          </div>
        </div>

        <div class="kpi-divider">
          <div class="stat-box result-enter" style="animation-delay: 70ms">
            <div class="lbl">Consumo de agua · 3 años</div>
            <div class="val"><span data-kpi-target="${waterM3}" data-kpi-kind="num" data-kpi-suffix=" m³">${NUM.format(waterM3)} m³</span></div>
            <div class="text-[11px] mt-1">${NUM.format(Math.round(basePlan.consumo_agua_litros || 0))} L · ${NUM.format(Math.round(basePlan.demanda_agua_efectiva_3a_mm || 0))} mm</div>
          </div>
          <div class="kpi-row result-enter" style="animation-delay: 140ms">
            <div class="stat-box">
              <div class="lbl">Utilidad neta</div>
              <div class="val" style="font-size:1.35rem"><span data-kpi-target="${netMxn}" data-kpi-kind="currency">${CURRENCY.format(netMxn)}</span></div>
              <div class="text-[11px] mt-1">${CURRENCY.format(basePlan.ingreso_neto_ha_3a_mxn)} / ha</div>
            </div>
            <div class="stat-box">
              <div class="lbl">Suelo cubierto</div>
              <div class="val" style="font-size:1.35rem">${bal.meses_suelo_protegido_3a}/36 m</div>
              <div class="text-[11px] mt-1">${bal.meses_suelo_desnudo_3a} meses desnudo</div>
            </div>
          </div>
        </div>

        <div class="result-enter" style="animation-delay: 140ms">
          <div class="field-label">Riesgo a 3 años</div>
          <div class="traffic-grid">
            ${trafficBox("Sequía", basePlan.semaforo_sequia)}
            ${trafficBox("Heladas", basePlan.semaforo_heladas)}
            ${trafficBox("Plagas", basePlan.semaforo_plagas)}
          </div>
        </div>

        <div>
          <details class="validation">
            <summary><span>Ver fundamento técnico NASA</span></summary>
            <div class="detail-body">
              <div>
                <div class="field-label">Calendario actual</div>
                <div class="table-scroll">
                  <table class="mini-table">
                    <thead><tr><th>Ciclo</th><th>Primavera-Verano</th><th>Otoño-Invierno</th></tr></thead>
                    <tbody>${rows}</tbody>
                  </table>
                </div>
              </div>
              <p class="nasa-note">${formatEvidenceText(basePlan.nasa_evidence_summary)}</p>
              ${renderOfficialVarietyMetaBlock(data)}
            </div>
          </details>
          <details class="validation">
            <summary><span>¿Qué no ve el satélite?</span></summary>
            <ul>${validationNotes}</ul>
          </details>
        </div>
      </article>
    `;
    icons();
    animateKPIs(baselineEl);
  }

  /* ---------- Step 5: Tus Opciones de Rotación (De lo Bueno a lo Óptimo) ---------- */
  function renderSolutions(data) {
    const basePlan = data.plans.find((p) => p.plan_id === "plan_actual") || data.plans[0];
    const alternatives = data.plans.filter((p) => p.plan_id !== "plan_actual");

    // Ordenar de menor a mayor afinidad: alternativa #5 arriba hasta la Mejor Opción (#1) abajo
    const sorted = [...alternatives].sort((a, b) => {
      if (a.rank != null && b.rank != null) return b.rank - a.rank;
      return a.suitability_score - b.suitability_score;
    });
    const haInfo = getHectareDisplay();
    const plansEl = $("plans");
    const RANK_BADGES = {
      1: "Mejor opción (#1 Recomendada)",
      2: "Segunda alternativa (#2)",
      3: "Tercera alternativa (#3)",
      4: "Cuarta alternativa (#4)",
      5: "Quinta alternativa (#5)",
    };

    plansEl.innerHTML = sorted
      .map((p, idx) => {
        const totalAlts = sorted.length;
        const displayRank = p.rank != null ? Number(p.rank) : totalAlts - idx;
        const isOptimal = displayRank === 1 || idx === totalAlts - 1;
        const delayMs = [0, 60, 120, 180, 240][idx] ?? idx * 60;
        const badgeLabel = RANK_BADGES[displayRank] || `Alternativa (#${displayRank})`;
        const bal = p.balance_nitrogeno_y_cobertura || {};
        const extraMoney = p.ingreso_neto_total_mxn - (basePlan ? basePlan.ingreso_neto_total_mxn : 0);
        const extraMoneyStr =
          extraMoney >= 0
            ? `+${CURRENCY.format(extraMoney)} extra vs. tu plan actual`
            : `${CURRENCY.format(extraMoney)} vs. tu plan actual`;
        const netMxn = Math.round(p.ingreso_neto_total_mxn || 0);
        const savedWaterM3 = Math.round(p.ahorro_agua_m3 || 0);

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
        <article class="card plan-card ${isOptimal ? "best" : ""} result-enter" style="animation-delay: ${delayMs}ms">
          ${isOptimal
            ? `<div class="best-tag"><i data-lucide="award" class="w-3.5 h-3.5"></i> ${badgeLabel}</div>`
            : `<div class="alt-tag"><i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i> ${badgeLabel}</div>`
          }

          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="plan-name">${p.plan_name}</h3>
              <p class="plan-focus"><span data-kpi-target="${haInfo.val}" data-kpi-kind="num" data-kpi-decimals="${haInfo.decimals}" data-kpi-suffix=" ha">${haInfo.text}</span> · ${p.strategy_focus}</p>
            </div>
            <div class="text-right shrink-0">
              <div class="score-big">${Math.round(p.suitability_score)}%</div>
              <div class="score-sub">afinidad</div>
            </div>
          </div>

          <div class="kpi-divider">
            <div class="stat-box">
              <div class="lbl">Utilidad neta · 3 años</div>
              <div class="val"><span data-kpi-target="${netMxn}" data-kpi-kind="currency">${CURRENCY.format(netMxn)}</span></div>
              <div class="text-[11px] mt-1">${extraMoneyStr}</div>
            </div>
            <div class="kpi-row">
              <div class="stat-box">
                <div class="lbl">Agua ahorrada</div>
                <div class="val" style="font-size:1.35rem"><span data-kpi-target="${savedWaterM3}" data-kpi-kind="num" data-kpi-suffix=" m³">${NUM.format(savedWaterM3)} m³</span></div>
                <div class="text-[11px] mt-1">${NUM.format(Math.round(p.ahorro_agua_litros || 0))} L</div>
              </div>
              <div class="stat-box">
                <div class="lbl">Salud del suelo</div>
                <div class="val" style="font-size:1.35rem">${bal.ciclos_fijacion_nitrogeno_3a} ciclos N</div>
                <div class="text-[11px] mt-1">${bal.meses_suelo_protegido_3a}/36 meses cubierto</div>
              </div>
            </div>
          </div>

          <div>
            <div class="field-label">Riesgo a 3 años</div>
            <div class="traffic-grid">
              ${trafficBox("Sequía", p.semaforo_sequia)}
              ${trafficBox("Heladas", p.semaforo_heladas)}
              ${trafficBox("Plagas", p.semaforo_plagas)}
            </div>
          </div>

          <div>
            <details class="validation">
              <summary><span>Ver rotación y fundamento técnico NASA</span></summary>
              <div class="detail-body">
                <div>
                  <div class="field-label">Rotación paso a paso</div>
                  <div class="table-scroll">
                    <table class="mini-table">
                      <thead><tr><th>Año</th><th>Primavera-Verano</th><th>Otoño-Invierno</th></tr></thead>
                      <tbody>${rows}</tbody>
                    </table>
                  </div>
                </div>
                <p class="nasa-note">${formatEvidenceText(p.nasa_evidence_summary)}</p>
                ${renderOfficialVarietyMetaBlock(data)}
              </div>
            </details>
            <details class="validation">
              <summary><span>Incertidumbres y validación local</span></summary>
              <ul>${validationNotes}</ul>
            </details>
          </div>
        </article>`;
      })
      .join("");

    const exportCard = document.querySelector("#step-6 > .card");
    if (exportCard) {
      exportCard.classList.remove("result-enter");
      void exportCard.offsetWidth;
      exportCard.style.animationDelay = `${Math.min(sorted.length, 5) * 60}ms`;
      exportCard.classList.add("result-enter");
    }

    icons();
    animateKPIs(plansEl);
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

    const baseRow = data.plans.find((p) => p.plan_id === "plan_actual");
    const altRowsSorted = data.plans
      .filter((p) => p.plan_id !== "plan_actual")
      .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99) || b.suitability_score - a.suitability_score);
    const orderedPlans = baseRow ? [baseRow, ...altRowsSorted] : altRowsSorted;

    const summaryRows = orderedPlans
      .map((p, idx) => {
        const isBase = p.plan_id === "plan_actual";
        const isRec = p.plan_id === data.recommended_plan_id;
        const rankNum = p.rank != null ? p.rank : (baseRow ? idx : idx + 1);
        const label = isBase
          ? `<b>${p.plan_name}</b> (Línea base)`
          : `<b>#${rankNum} · ${p.plan_name}</b> ${isRec ? "(Mejor Opción · " : "("}${Math.round(p.suitability_score)}%)`;
        const waterStr = isBase
          ? `Consumo base: ${NUM.format(Math.round(p.consumo_agua_litros || 0))} L`
          : `Ahorro: ${NUM.format(Math.round(p.ahorro_agua_litros || 0))} L`;
        const bal = p.balance_nitrogeno_y_cobertura || {};
        return `
        <tr>
          <td>${label}</td>
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
          <div class="ps-title">Kultiva — Hoja de Ruta para Campo (3 Años)</div>
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
        <div><b>Cultivo Actual / Base (Año 1):</b> ${escapeHtml(data.nombre_comun || data.current_crop_label || state.currentCrop)} (${escapeHtml(data.current_crop_cycle_label || "")
      })</div>
        <div><b>Fuente Oficial Variedad:</b> ${escapeHtml(data.fuente_oficial || "Catálogo oficial Kultiva Coahuila")}</div>
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

      <div class="ps-h">3. Comparativa Top 5 de Planes a 3 Años vs. Línea Base (${NUM.format(state.hectares)} ha)</div>
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
        `${locName} · 2016–2026 · Lluvia GPM ${gpmTip} vs. NDVI ${ndviTip}`;
    } else {
      $("chart-subtitle").innerHTML =
        `${locName} · 12 meses · Lluvia GPM ${gpmTip} vs. NDVI ${ndviTip}`;
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
    let d;
    try {
      const res = await fetch("/api/init");
      if (!res.ok) throw new Error("init failed");
      d = await res.json();
    } catch (err) {
      if (window.KultivaOffline && typeof window.KultivaOffline.getInitPayload === "function") {
        d = window.KultivaOffline.getInitPayload();
      } else {
        throw err;
      }
    }
    state.suelos = Object.fromEntries(d.suelos.map((s) => [s.location_id, s]));
    state.cultivos = d.cultivos || [];
    state.familias = d.familias_cultivo || [];
    state.catalogoAgrupado = d.catalogo_agrupado || [];
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

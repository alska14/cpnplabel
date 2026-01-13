const el = (id) => document.getElementById(id);

const fields = {
  product_name: el("productName"),
  function_claim: el("functionClaim"),
  usage_instructions: el("usageInstructions"),
  warnings_precautions: el("warningsPrecautions"),
  inci_ingredients: el("inciIngredients"),
  distributor: el("distributor"),
  eu_responsible_person: el("euResponsiblePerson"),
  country_of_origin: el("countryOfOrigin"),
  batch_lot: el("batchLot"),
  expiry_date: el("expiryDate"),
  net_content: el("netContent"),
};

const status = el("status");
const rawText = el("rawText");
const labelPreview = el("labelPreview");
const progress = el("progress");
const toast = el("toast");
const historyList = el("historyList");
const clearHistory = el("clearHistory");
const dropzone = el("dropzone");
const fileInput = el("fileInput");
const langOptions = el("langOptions");
const translateBtn = el("translateBtn");
const langTabs = el("langTabs");

const defaultRp =
  "YJN Europe s.r.o.\n6F, M.R. Stefanika, 010 01, Zilina, Slovak Republic";

fields.eu_responsible_person.value = defaultRp;
fields.country_of_origin.value = "Made in Korea";

const DEFAULT_API_BASE = "https://cpsr-label-weauxnazsq-du.a.run.app";

const getApiBase = () => {
  const raw = el("apiBase").value.trim();
  return raw ? raw.replace(/\/$/, "") : DEFAULT_API_BASE;
};

el("apiBase").value = DEFAULT_API_BASE;

const escapeHtml = (value) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const oneLine = (text) => text.replace(/\s+/g, " ").trim();

const buildLabelText = () => {
  const distributorFallback =
    "Distributor 정보가 없을 경우, 유럽 유통용 최종 라벨 검토 불가.";
  const distributorValue = fields.distributor.value.trim();
  const distributorText = distributorValue || distributorFallback;

  const lines = [
    "YJN Partners CPSR Label Example",
    "",
    "1. Product Name:",
    fields.product_name.value || "N/A",
    "",
    "2. Product Function:",
    fields.function_claim.value || "N/A",
    "",
    "3. How to Use:",
    fields.usage_instructions.value || "N/A",
    "",
    "4. Warning / Precautions:",
    fields.warnings_precautions.value || "N/A",
    "",
    "5. Ingredients (INCI):",
    fields.inci_ingredients.value || "N/A",
    "",
    "6. Expiry Date:",
    fields.expiry_date.value || "Shown on the package",
    "",
    "7. EU Responsible Person:",
    fields.eu_responsible_person.value || defaultRp,
    "",
    "8. Distributor Name and Address:",
    distributorText,
    "",
    "9. Country of Origin:",
    fields.country_of_origin.value || "Made in Korea",
    "",
    "10. Batch Number:",
    fields.batch_lot.value || "Shown on the package",
    "",
    "11. Nominal Quantities:",
    fields.net_content.value || "N/A",
  ];

  return lines.join("\n");
};

const updatePreview = () => {
  const selected = getSelectedLangs();
  if (!selected.length) {
    if (langTabs) {
      langTabs.innerHTML = "";
    }
    labelPreview.textContent = buildLabelText();
    return;
  }

  if (!activeLang || !selected.includes(activeLang)) {
    activeLang = selected[0];
  }

  renderTabs(selected);
  const labelText = buildLabelTextForLang(activeLang);
  labelPreview.innerHTML = `<strong>${LANGUAGE_TITLES[activeLang]}</strong><br /><br />${labelText}`;
};

const setProgress = (active, message) => {
  if (message) {
    status.textContent = message;
  }
  if (active) {
    progress.classList.add("active");
  } else {
    progress.classList.remove("active");
  }
};

const showToast = (message) => {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => {
    toast.classList.remove("show");
  }, 2200);
};

let historyCache = [];
let translations = {};
let activeLang = "";

const renderTabs = (langs) => {
  if (!langTabs) {
    return;
  }
  langTabs.innerHTML = "";
  if (!langs.length) {
    return;
  }
  langs.forEach((lang) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lang-tab";
    btn.dataset.lang = lang;
    btn.textContent = LANGUAGE_TITLES[lang] || lang;
    if (lang === activeLang) {
      btn.classList.add("active");
    }
    langTabs.appendChild(btn);
  });
};

const renderHistory = (items) => {
  historyList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "history-meta";
    empty.textContent = "아직 저장된 기록이 없습니다.";
    historyList.appendChild(empty);
    return;
  }
  items.forEach((item, index) => {
    const card = document.createElement("div");
    card.className = "history-item";
    card.dataset.index = String(index);
    card.innerHTML = `
      <div class="history-content">
        <p class="history-title">${item.title}</p>
        <p class="history-meta">${item.meta}</p>
      </div>
      <button class="history-delete" type="button" data-id="${item.id || ""}">삭제</button>
    `;
    historyList.appendChild(card);
  });
};

const getHistory = () => historyCache.slice(0);

const applyHistoryItem = (item) => {
  fields.product_name.value = item.form.product_name || "";
  fields.function_claim.value = item.form.function_claim || "";
  fields.usage_instructions.value = item.form.usage_instructions || "";
  fields.warnings_precautions.value = item.form.warnings_precautions || "";
  fields.inci_ingredients.value = item.form.inci_ingredients || "";
  fields.distributor.value = item.form.distributor || "";
  fields.eu_responsible_person.value =
    item.form.eu_responsible_person || defaultRp;
  fields.country_of_origin.value = item.form.country_of_origin || "Made in Korea";
  fields.batch_lot.value = item.form.batch_lot || "";
  fields.expiry_date.value = item.form.expiry_date || "";
  fields.net_content.value = item.form.net_content || "";
  rawText.textContent = item.raw_text || "";
  translations = {};
  updatePreview();
  showToast("저장된 분석을 불러왔습니다.");
  const parsedSection = document.getElementById("parsedSection");
  if (parsedSection) {
    parsedSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
};

const fetchHistory = async () => {
  const apiBase = getApiBase();
  if (!apiBase) {
    return;
  }
  try {
    const resp = await fetch(`${apiBase}/api/history`);
    if (!resp.ok) {
      throw new Error("history fetch failed");
    }
    const data = await resp.json();
    historyCache = data.items || [];
    renderHistory(historyCache);
  } catch {
    showToast("히스토리를 불러오지 못했습니다.");
  }
};

const addHistoryItem = async (item) => {
  const apiBase = getApiBase();
  if (!apiBase) {
    return;
  }
  try {
    const resp = await fetch(`${apiBase}/api/history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(item),
    });
    if (!resp.ok) {
      throw new Error("history add failed");
    }
    const data = await resp.json();
    historyCache = data.items || [];
    renderHistory(historyCache);
  } catch {
    showToast("히스토리 저장에 실패했습니다.");
  }
};

const LANGUAGE_TITLES = {
  en: "English",
  de: "Deutsch",
  fr: "Français",
  it: "Italiano",
  es: "Español",
};

const LABELS = {
  en: {
    title: "YJN Partners CPSR Label Example",
    product_name: "1. Product Name:",
    function_claim: "2. Product Function:",
    usage: "3. How to Use:",
    warnings: "4. Warning / Precautions:",
    ingredients: "5. Ingredients (INCI):",
    expiry: "6. Expiry Date:",
    rp: "7. EU Responsible Person:",
    distributor: "8. Distributor Name and Address:",
    origin: "9. Country of Origin:",
    batch: "10. Batch Number:",
    net: "11. Nominal Quantities:",
    distributor_warning:
      "Distributor info required. Final EU distribution label review not possible.",
  },
  de: {
    title: "YJN Partners CPSR Etikettbeispiel",
    product_name: "1. Produktname:",
    function_claim: "2. Produktfunktion:",
    usage: "3. Anwendung:",
    warnings: "4. Warnhinweise / Vorsichtsmaßnahmen:",
    ingredients: "5. Inhaltsstoffe (INCI):",
    expiry: "6. Mindesthaltbarkeitsdatum:",
    rp: "7. EU Verantwortliche Person:",
    distributor: "8. Vertrieb / Adresse:",
    origin: "9. Herkunftsland:",
    batch: "10. Chargennummer:",
    net: "11. Nenninhalt:",
    distributor_warning:
      "Distributor info required. Final EU distribution label review not possible.",
  },
  fr: {
    title: "Exemple d’étiquette CPSR YJN Partners",
    product_name: "1. Nom du produit :",
    function_claim: "2. Fonction du produit :",
    usage: "3. Mode d’emploi :",
    warnings: "4. Avertissements / Précautions :",
    ingredients: "5. Ingrédients (INCI) :",
    expiry: "6. Date d’expiration :",
    rp: "7. Personne responsable UE :",
    distributor: "8. Distributeur / Adresse :",
    origin: "9. Pays d’origine :",
    batch: "10. Numéro de lot :",
    net: "11. Contenu nominal :",
    distributor_warning:
      "Distributor info required. Final EU distribution label review not possible.",
  },
  it: {
    title: "Esempio etichetta CPSR YJN Partners",
    product_name: "1. Nome del prodotto:",
    function_claim: "2. Funzione del prodotto:",
    usage: "3. Modalità d’uso:",
    warnings: "4. Avvertenze / Precauzioni:",
    ingredients: "5. Ingredienti (INCI):",
    expiry: "6. Data di scadenza:",
    rp: "7. Persona responsabile UE:",
    distributor: "8. Distributore / Indirizzo:",
    origin: "9. Paese d’origine:",
    batch: "10. Numero di lotto:",
    net: "11. Quantità nominali:",
    distributor_warning:
      "Distributor info required. Final EU distribution label review not possible.",
  },
  es: {
    title: "Ejemplo de etiqueta CPSR YJN Partners",
    product_name: "1. Nombre del producto:",
    function_claim: "2. Función del producto:",
    usage: "3. Modo de uso:",
    warnings: "4. Advertencias / Precauciones:",
    ingredients: "5. Ingredientes (INCI):",
    expiry: "6. Fecha de caducidad:",
    rp: "7. Persona responsable UE:",
    distributor: "8. Distribuidor / Dirección:",
    origin: "9. País de origen:",
    batch: "10. Número de lote:",
    net: "11. Cantidades nominales:",
    distributor_warning:
      "Distributor info required. Final EU distribution label review not possible.",
  },
};

const getSelectedLangs = () =>
  Array.from(langOptions.querySelectorAll("input:checked")).map(
    (input) => input.value
  );

const getTranslateFields = () => ({
  product_name: fields.product_name.value,
  function_claim: fields.function_claim.value,
  usage_instructions: fields.usage_instructions.value,
  warnings_precautions: fields.warnings_precautions.value,
  expiry_date: fields.expiry_date.value,
  country_of_origin: fields.country_of_origin.value,
  batch_lot: fields.batch_lot.value,
  net_content: fields.net_content.value,
});

const buildLabelTextForLang = (lang) => {
  const labels = LABELS[lang] || LABELS.en;
  const translated = translations[lang] || {};
  const distributorValue = fields.distributor.value.trim();
  const distributorText = distributorValue || labels.distributor_warning;
  const distributorRendered = distributorValue
    ? escapeHtml(distributorText)
    : `<span class="warning">${escapeHtml(distributorText)}</span>`;

  const lines = [
    escapeHtml(labels.title),
    "",
    `${escapeHtml(labels.product_name)}<br />${escapeHtml(
      translated.product_name || "(번역 필요)"
    )}`,
    "",
    `${escapeHtml(labels.function_claim)}<br />${escapeHtml(
      translated.function_claim || "(번역 필요)"
    )}`,
    "",
    `${escapeHtml(labels.usage)}<br />${escapeHtml(
      translated.usage_instructions || "(번역 필요)"
    )}`,
    "",
    `${escapeHtml(labels.warnings)}<br />${escapeHtml(
      translated.warnings_precautions || "(번역 필요)"
    )}`,
    "",
    `${escapeHtml(labels.ingredients)}<br />${escapeHtml(
      fields.inci_ingredients.value || "N/A"
    )}`,
    "",
    `${escapeHtml(labels.expiry)}<br />${escapeHtml(
      translated.expiry_date || "(번역 필요)"
    )}`,
    "",
    `${escapeHtml(labels.rp)}<br />${escapeHtml(
      fields.eu_responsible_person.value || defaultRp
    )}`,
    "",
    `${escapeHtml(labels.distributor)}<br />${distributorRendered}`,
    "",
    `${escapeHtml(labels.origin)}<br />${escapeHtml(
      translated.country_of_origin || "(번역 필요)"
    )}`,
    "",
    `${escapeHtml(labels.batch)}<br />${escapeHtml(
      translated.batch_lot || "(번역 필요)"
    )}`,
    "",
    `${escapeHtml(labels.net)}<br />${escapeHtml(
      translated.net_content || "(번역 필요)"
    )}`,
  ];

  return lines.join("<br />");
};

const startOcrSteps = () => {
  const steps = [
    "파일 업로드 중...",
    "OCR 요청 중...",
    "OCR 처리 중...",
    "결과 수신 중...",
  ];
  let index = 0;
  setProgress(true, steps[index]);
  const interval = window.setInterval(() => {
    index = (index + 1) % steps.length;
    setProgress(true, steps[index]);
  }, 1800);
  return () => window.clearInterval(interval);
};

const setSelectedFile = (file) => {
  if (file) {
    status.textContent = `선택됨: ${file.name}`;
  }
};

Object.values(fields).forEach((input) => {
  input.addEventListener("input", updatePreview);
  input.addEventListener("input", () => {
    translations = {};
    activeLang = "";
  });
});

updatePreview();
fetchHistory();

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  setSelectedFile(file);
});

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("active");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("active");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("active");
  const file = event.dataTransfer.files[0];
  if (!file) {
    return;
  }
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;
  setSelectedFile(file);
});

el("btnOcr").addEventListener("click", async () => {
  const file = fileInput.files[0];
  const apiBase = getApiBase();
  if (!file) {
    status.textContent = "먼저 파일을 선택해 주세요.";
    return;
  }
  if (!apiBase) {
    status.textContent = "API 주소가 설정되지 않았습니다.";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  const stopSteps = startOcrSteps();
  rawText.textContent = "";

  try {
    const resp = await fetch(`${apiBase}/api/ocr`, {
      method: "POST",
      body: formData,
    });

    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(detail || "OCR failed");
    }

    const data = await resp.json();
    rawText.textContent = data.raw_text || "";

    const parsed = data.parsed || {};
    fields.product_name.value = parsed.product_name || "";
    const description = (parsed.description || "").trim();
    const functionClaim = (parsed.function_claim || "").trim();
    if (description && functionClaim) {
      fields.function_claim.value = `${description} / ${functionClaim}`;
    } else {
      fields.function_claim.value = description || functionClaim || "";
    }
    fields.usage_instructions.value = parsed.usage_instructions || "";
    fields.warnings_precautions.value = parsed.warnings_precautions || "";
    fields.inci_ingredients.value = parsed.inci_ingredients || "";
    fields.net_content.value = parsed.net_content || "";
    fields.expiry_date.value = parsed.expiry_date || "";
    fields.batch_lot.value = parsed.batch_lot || "";
    fields.country_of_origin.value = parsed.country_of_origin || "Made in Korea";
    if (parsed.responsible_person) {
      fields.eu_responsible_person.value = parsed.responsible_person;
    }

    translations = {};
    updatePreview();
    stopSteps();
    setProgress(false, "OCR 완료. 내용을 확인해 주세요.");
    showToast("OCR 분석이 완료되었습니다.");
    const parsedSection = document.getElementById("parsedSection");
    if (parsedSection) {
      parsedSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    addHistoryItem({
      title: fields.product_name.value || file.name,
      meta: new Date().toLocaleString("ko-KR"),
      raw_text: data.raw_text || "",
      form: {
        product_name: fields.product_name.value,
        function_claim: fields.function_claim.value,
        usage_instructions: fields.usage_instructions.value,
        warnings_precautions: fields.warnings_precautions.value,
        inci_ingredients: fields.inci_ingredients.value,
        distributor: fields.distributor.value,
        eu_responsible_person: fields.eu_responsible_person.value,
        country_of_origin: fields.country_of_origin.value,
        batch_lot: fields.batch_lot.value,
        expiry_date: fields.expiry_date.value,
        net_content: fields.net_content.value,
      },
    });
  } catch (err) {
    stopSteps();
    setProgress(false, `OCR 오류: ${err.message}`);
  }
});

translateBtn.addEventListener("click", async () => {
  const targets = getSelectedLangs();
  if (!targets.length) {
    showToast("번역할 언어를 선택해 주세요.");
    return;
  }
  const apiBase = getApiBase();
  const payload = {
    targets,
    fields: getTranslateFields(),
  };
  setProgress(true, "번역 중...");
  try {
    const resp = await fetch(`${apiBase}/api/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(detail || "Translate failed");
    }
    const data = await resp.json();
    translations = data.translations || {};
    activeLang = targets[0] || "";
    setProgress(false, "번역 완료.");
    updatePreview();
  } catch (err) {
    setProgress(false, `번역 오류: ${err.message}`);
  }
});

if (langTabs) {
  langTabs.addEventListener("click", (event) => {
    const button = event.target.closest(".lang-tab");
    if (!button) {
      return;
    }
    activeLang = button.dataset.lang || "";
    updatePreview();
  });
}

historyList.addEventListener("click", (event) => {
  const deleteBtn = event.target.closest(".history-delete");
  if (deleteBtn) {
    const id = deleteBtn.dataset.id;
    if (!id) {
      return;
    }
    const apiBase = getApiBase();
    fetch(`${apiBase}/api/history/${id}`, { method: "DELETE" })
      .then((resp) => {
        if (!resp.ok) {
          throw new Error("delete failed");
        }
        return resp.json();
      })
      .then((data) => {
        historyCache = data.items || [];
        renderHistory(historyCache);
        showToast("항목이 삭제되었습니다.");
      })
      .catch(() => {
        showToast("삭제에 실패했습니다.");
      });
    return;
  }
  const target = event.target.closest(".history-item");
  if (!target) {
    return;
  }
  const items = getHistory();
  const index = Number(target.dataset.index);
  const item = items[index];
  if (item) {
    applyHistoryItem(item);
  }
});

clearHistory.addEventListener("click", () => {
  const apiBase = getApiBase();
  if (!apiBase) {
    return;
  }
  fetch(`${apiBase}/api/history`, { method: "DELETE" })
    .then((resp) => {
      if (!resp.ok) {
        throw new Error("clear failed");
      }
      return resp.json();
    })
    .then(() => {
      historyCache = [];
      renderHistory([]);
      showToast("히스토리를 비웠습니다.");
    })
    .catch(() => {
      showToast("히스토리 삭제에 실패했습니다.");
    });
});

el("btnPdf").addEventListener("click", async () => {
  const apiBase = getApiBase();
  if (!apiBase) {
    status.textContent = "API 주소가 설정되지 않았습니다.";
    return;
  }

  const selectedLangs = getSelectedLangs();
  if (selectedLangs.length) {
    const missing = selectedLangs.filter((lang) => !translations[lang]);
    if (missing.length) {
      showToast("먼저 번역을 적용해 주세요.");
      return;
    }
    const sections = selectedLangs.map((lang) => ({
      title: LANGUAGE_TITLES[lang] || lang,
      text: buildLabelTextForLang(lang).replace(/<br\s*\/?>/g, "\n"),
    }));

    setProgress(true, "PDF 생성 중...");
    try {
      const resp = await fetch(`${apiBase}/api/pdf-multi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sections }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(detail || "PDF generation failed");
      }
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${fields.product_name.value || "label"}_multi.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setProgress(false, "PDF 생성 완료.");
    } catch (err) {
      setProgress(false, `PDF 오류: ${err.message}`);
    }
    return;
  }

  const payload = {
    product_name: fields.product_name.value,
    function_claim: fields.function_claim.value,
    usage_instructions: fields.usage_instructions.value,
    warnings_precautions: fields.warnings_precautions.value,
    inci_ingredients: fields.inci_ingredients.value,
    distributor: fields.distributor.value,
    eu_responsible_person: fields.eu_responsible_person.value,
    country_of_origin: fields.country_of_origin.value,
    batch_lot: fields.batch_lot.value,
    expiry_date: fields.expiry_date.value,
    net_content: fields.net_content.value,
  };

  setProgress(true, "PDF 생성 중...");

  try {
    const resp = await fetch(`${apiBase}/api/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(detail || "PDF generation failed");
    }

    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${payload.product_name || "label"}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);

    setProgress(false, "PDF 생성 완료.");
  } catch (err) {
    setProgress(false, `PDF 오류: ${err.message}`);
  }
});

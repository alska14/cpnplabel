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

const buildLabelLines = () => {
  const distributorFallback =
    "Distributor 정보가 없을 경우, 유럽 유통용 최종 라벨 검토 불가.";
  const distributorValue = fields.distributor.value.trim();
  const distributorText = distributorValue || distributorFallback;

  return [
    { label: "YJN Partners CPSR Label Example", value: "" },
    { label: "1. Product Name:", value: fields.product_name.value || "N/A" },
    { label: "2. Product Function:", value: fields.function_claim.value || "N/A" },
    { label: "3. How to Use:", value: fields.usage_instructions.value || "N/A" },
    { label: "4. Warning / Precautions:", value: fields.warnings_precautions.value || "N/A" },
    { label: "5. Ingredients (INCI):", value: fields.inci_ingredients.value || "N/A" },
    { label: "6. Expiry Date:", value: fields.expiry_date.value || "Shown on the package" },
    { label: "7. EU Responsible Person:", value: fields.eu_responsible_person.value || defaultRp },
    {
      label: "8. Distributor Name and Address:",
      value: oneLine(distributorText),
      isWarning: !distributorValue,
    },
    { label: "9. Country of Origin:", value: fields.country_of_origin.value || "Made in Korea" },
    { label: "10. Batch Number:", value: fields.batch_lot.value || "Shown on the package" },
    { label: "11. Nominal Quantities:", value: fields.net_content.value || "N/A" },
  ];
};

const updatePreview = () => {
  const lines = buildLabelLines();
  const html = lines
    .map((line, idx) => {
      if (idx === 0) {
        return escapeHtml(line.label);
      }
      const value = line.isWarning
        ? `<span class="warning">${escapeHtml(line.value)}</span>`
        : escapeHtml(line.value);
      return `${escapeHtml(line.label)}<br />${value}`;
    })
    .join("<br /><br />");
  labelPreview.innerHTML = html;
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

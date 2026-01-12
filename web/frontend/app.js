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

const defaultRp =
  "YJN Europe s.r.o.\n6F, M.R. Stefanika, 010 01, Zilina, Slovak Republic";

fields.eu_responsible_person.value = defaultRp;
fields.country_of_origin.value = "Made in Korea";

const buildLabelText = () => {
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
    fields.distributor.value || "Distributor info required.",
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
  labelPreview.textContent = buildLabelText();
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

Object.values(fields).forEach((input) => {
  input.addEventListener("input", updatePreview);
});

updatePreview();

const DEFAULT_API_BASE = "https://cpsr-label-weauxnazsq-du.a.run.app";

const getApiBase = () => {
  const raw = el("apiBase").value.trim();
  return raw ? raw.replace(/\/$/, "") : DEFAULT_API_BASE;
};

el("apiBase").value = DEFAULT_API_BASE;

el("btnOcr").addEventListener("click", async () => {
  const file = el("fileInput").files[0];
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

  setProgress(true, "파일 업로드 중...");
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

    setProgress(true, "OCR 처리 중...");
    const data = await resp.json();
    rawText.textContent = data.raw_text || "";

    const parsed = data.parsed || {};
    fields.product_name.value = parsed.product_name || "";
    fields.function_claim.value = parsed.function_claim || "";
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
    setProgress(false, "OCR 완료. 내용을 확인해 주세요.");
    showToast("OCR 분석이 완료되었습니다.");
    const parsedSection = document.getElementById("parsedSection");
    if (parsedSection) {
      parsedSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (err) {
    setProgress(false, `OCR 오류: ${err.message}`);
  }
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

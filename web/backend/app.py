import io
import os
import re
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from google.cloud import vision
from google.cloud import storage
from google.cloud import firestore
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
DEFAULT_EU_RP = "YJN Europe s.r.o.\n6F, M.R. Stefanika, 010 01, Zilina, Slovak Republic"
HISTORY_COLLECTION = "ocr_history"
HISTORY_LIMIT = 10

app = FastAPI(title="CPSR Label Web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LabelForm(BaseModel):
    product_name: str = ""
    function_claim: str = ""
    usage_instructions: str = ""
    warnings_precautions: str = ""
    inci_ingredients: str = ""
    distributor: str = ""
    eu_responsible_person: str = DEFAULT_EU_RP
    country_of_origin: str = "Made in Korea"
    batch_lot: str = ""
    expiry_date: str = ""
    net_content: str = ""


def _vision_client() -> vision.ImageAnnotatorClient:
    if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
        return vision.ImageAnnotatorClient.from_service_account_json(SERVICE_ACCOUNT_FILE)
    return vision.ImageAnnotatorClient()


def _storage_client() -> storage.Client:
    if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
        return storage.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)
    return storage.Client()


def _firestore_client() -> firestore.Client:
    if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
        return firestore.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)
    return firestore.Client()


def _fetch_history_items(db: firestore.Client) -> List[Dict[str, Any]]:
    docs = (
        db.collection(HISTORY_COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(HISTORY_LIMIT)
        .stream()
    )
    items: List[Dict[str, Any]] = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        items.append(data)
    return items


def _trim_history(db: firestore.Client) -> None:
    docs = (
        db.collection(HISTORY_COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .offset(HISTORY_LIMIT)
        .stream()
    )
    for doc in docs:
        doc.reference.delete()


@app.get("/api/history")
def get_history():
    db = _firestore_client()
    items = _fetch_history_items(db)
    return JSONResponse({"items": items})


@app.post("/api/history")
def add_history(payload: Dict[str, Any]):
    db = _firestore_client()
    record = {
        "title": payload.get("title", ""),
        "meta": payload.get("meta", ""),
        "raw_text": payload.get("raw_text", ""),
        "form": payload.get("form", {}),
        "created_at": datetime.now(timezone.utc),
    }
    db.collection(HISTORY_COLLECTION).add(record)
    _trim_history(db)
    items = _fetch_history_items(db)
    return JSONResponse({"items": items})


@app.delete("/api/history")
def clear_history():
    db = _firestore_client()
    docs = db.collection(HISTORY_COLLECTION).stream()
    for doc in docs:
        doc.reference.delete()
    return JSONResponse({"items": []})


def _upload_to_gcs(storage_client: storage.Client, file_path: str, bucket_name: str) -> str:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(os.path.basename(file_path))
    blob.upload_from_filename(file_path)
    return f"gs://{bucket_name}/{os.path.basename(file_path)}"


def _call_ocr_api(file_path: str) -> str:
    vision_client = _vision_client()
    storage_client = _storage_client()

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"]:
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            image = vision.Image(content=content)
            response = vision_client.document_text_detection(image=image)
            if response.error.message:
                return f"[ERROR] Vision API error: {response.error.message}"
            if response.full_text_annotation.text:
                return response.full_text_annotation.text
            if response.text_annotations:
                return response.text_annotations[0].description
            return "[NO_RESULT]"
        except Exception as exc:
            return f"[ERROR] Image OCR failed: {exc}"

    if not GCS_BUCKET_NAME:
        return "[ERROR] Missing GCS bucket name."

    try:
        gcs_uri = _upload_to_gcs(storage_client, file_path, GCS_BUCKET_NAME)
    except Exception as exc:
        return f"[ERROR] GCS upload failed: {exc}"

    prefix = f"{os.path.basename(file_path)}_output_{int(time.time())}/"
    destination_uri = f"gs://{GCS_BUCKET_NAME}/{prefix}"

    mime_type = "application/pdf"
    if ext in [".tif", ".tiff"]:
        mime_type = "image/tiff"

    input_config = vision.InputConfig(
        gcs_source=vision.GcsSource(uri=gcs_uri),
        mime_type=mime_type,
    )
    output_config = vision.OutputConfig(
        gcs_destination=vision.GcsDestination(uri=destination_uri),
        batch_size=1,
    )

    request = vision.AsyncAnnotateFileRequest(
        input_config=input_config,
        features=[vision.Feature(type=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)],
        output_config=output_config,
    )

    try:
        operation = vision_client.async_batch_annotate_files(requests=[request])
        operation.result(timeout=600)
    except Exception as exc:
        return f"[ERROR] Async OCR failed: {exc}"

    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    json_blobs = list(bucket.list_blobs(prefix=prefix))
    json_blobs = [b for b in json_blobs if b.name.endswith(".json")]
    if not json_blobs:
        return "[NO_RESULT]"

    json_blobs.sort(key=lambda b: b.name)
    full_text = ""
    try:
        for blob in json_blobs:
            text = blob.download_as_bytes().decode("utf-8")
            parsed = json.loads(text)
            for resp in parsed.get("responses", []):
                if "fullTextAnnotation" in resp:
                    full_text += resp["fullTextAnnotation"].get("text", "") + "\n"
    except Exception as exc:
        return f"[ERROR] JSON parse failed: {exc}"
    finally:
        try:
            for blob in json_blobs:
                blob.delete()
            bucket.blob(os.path.basename(file_path)).delete()
        except Exception:
            pass

    return full_text.strip() if full_text.strip() else "[NO_RESULT]"


def _clean_field_text(text: str) -> str:
    if not text:
        return ""
    value = re.sub(r"\s+", " ", text).strip()
    value = re.sub(
        r"^(Product\s*Name|Description|Claim/Function|Function|Marketing\s*Claim/Function|Marketing\s*Claim|How\s*to\s*use|Warning|Responsible\s*Person|Ingredients|Net\s*Content)[:\-\s]+\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip()


def _extract_field(start_pattern: str, end_pattern: str, text: str) -> str:
    regex = r"(" + start_pattern + r")\s*[:=\-\s]*(.*?)(?=\s*" + end_pattern + r"|\Z)"
    match = re.search(regex, text, re.IGNORECASE | re.DOTALL)
    return _clean_field_text(match.group(2)) if match else ""


def parse_ocr_text(ocr_text: str) -> Dict[str, Any]:
    if ocr_text.startswith(("[ERROR]", "[NO_RESULT]")):
        return {"error": ocr_text}

    cleaned = re.sub(r"[\r\n]+", " ", ocr_text)
    m_section = re.search(
        r"Labelled warnings and instructions of use(.*?)(Reasoning|Assessor|Annex|\Z)",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    section = m_section.group(1).strip() if m_section else cleaned

    data: Dict[str, Any] = {
        "product_name": _extract_field(r"Label\w* Information", r"Description", section),
        "description": _extract_field(r"Description", r"Marketing", section),
        "function_claim": _extract_field(r"Marketing", r"How to use", section),
        "usage_instructions": _extract_field(r"How to use", r"Warning", section),
        "warnings_precautions": _extract_field(r"Warning", r"Responsible|Ingredients", section),
        "responsible_person": _extract_field(r"Responsible", r"Ingredients", section),
        "inci_ingredients": _extract_field(r"Ingredients", r"Net Content", section),
        "net_content": "",
        "batch_lot": "",
        "expiry_date": "",
        "country_of_origin": "",
    }

    net = _extract_field(r"Net Content", r"Warning|$", section)
    if net:
        m_nc = re.search(r"(\d+\s*(ml|mL|g|G))", net)
        if m_nc:
            data["net_content"] = m_nc.group(1)
        m_exp = re.search(r"Best Before.*?:\s*(.*?)(,|$)", net)
        if m_exp:
            data["expiry_date"] = m_exp.group(1).strip()
        m_lot = re.search(r"LOT\s*:\s*(.*?)(,|$)", net)
        if m_lot:
            data["batch_lot"] = m_lot.group(1).strip()
        m_origin = re.search(r"Origin\s*:\s*(.*?)(,|$)", net)
        if m_origin:
            val = m_origin.group(1).strip()
            val = re.sub(r"\s+\d{1,3}$", "", val)
            data["country_of_origin"] = val

    if not data["product_name"] and "UNICONIC SHIELD FIXER" in cleaned:
        data["product_name"] = "SELF BEAUTY UNICONIC SHIELD FIXER"

    return data


def build_label_text(form: LabelForm) -> str:
    lines = [
        "YJN Partners CPSR Label Example",
        "",
        "1. Product Name:",
        form.product_name or "N/A",
        "",
        "2. Product Function:",
        form.function_claim or "N/A",
        "",
        "3. How to Use:",
        form.usage_instructions or "N/A",
        "",
        "4. Warning / Precautions:",
        form.warnings_precautions or "N/A",
        "",
        "5. Ingredients (INCI):",
        form.inci_ingredients or "N/A",
        "",
        "6. Expiry Date:",
        form.expiry_date or "Shown on the package",
        "",
        "7. EU Responsible Person:",
        form.eu_responsible_person or DEFAULT_EU_RP,
        "",
        "8. Distributor Name and Address:",
        form.distributor or "Distributor info required.",
        "",
        "9. Country of Origin:",
        form.country_of_origin or "Made in Korea",
        "",
        "10. Batch Number:",
        form.batch_lot or "Shown on the package",
        "",
        "11. Nominal Quantities:",
        form.net_content or "N/A",
    ]
    return "\n".join(lines)


def _draw_multiline_text(pdf: canvas.Canvas, text: str, x: float, y: float, max_width: float, leading: float = 14) -> float:
    for raw_line in text.split("\n"):
        line = raw_line
        while line:
            if pdf.stringWidth(line) <= max_width:
                pdf.drawString(x, y, line)
                y -= leading
                break
            cut = len(line)
            while cut > 0 and pdf.stringWidth(line[:cut]) > max_width:
                cut -= 1
            pdf.drawString(x, y, line[:cut])
            y -= leading
            line = line[cut:].lstrip()
    return y


def generate_pdf(form: LabelForm) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    y = height - margin

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin, y, "CPSR Label Example")
    y -= 18

    pdf.setFont("Helvetica", 11)
    label_text = build_label_text(form)
    y = _draw_multiline_text(pdf, label_text, margin, y, width - 2 * margin, leading=14)

    if y < margin:
        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return buffer.read()


@app.post("/api/ocr")
async def ocr(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    temp_dir = os.path.join(BASE_DIR, "tmp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"upload_{int(time.time())}{ext}")

    try:
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        ocr_text = _call_ocr_api(temp_path)
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

    parsed = parse_ocr_text(ocr_text)
    return JSONResponse({"raw_text": ocr_text, "parsed": parsed})


@app.post("/api/pdf")
async def create_pdf(form: LabelForm):
    pdf_bytes = generate_pdf(form)
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf")

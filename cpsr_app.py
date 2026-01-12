import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import os
import re
import time
from google.cloud import vision
from google.cloud import storage
from typing import Dict, Any
import json
from PIL import Image, ImageDraw, ImageFont, ImageTk

# ======================================================================
# 폰트 로딩
# ======================================================================
try:
    font_title = ImageFont.truetype("malgunbd.ttf", 36)
    font_bold = ImageFont.truetype("malgunbd.ttf", 24)
    font_reg = ImageFont.truetype("malgun.ttf", 22)
except:
    font_title = ImageFont.load_default()
    font_bold = ImageFont.load_default()
    font_reg = ImageFont.load_default()

print(ImageFont.truetype("malgun.ttf", 22))  # 폰트 정상 로딩 출력

# ======================================================================
# 설정
# ======================================================================
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

SERVICE_ACCOUNT_FILE = 'service-account-key.json'
GCS_BUCKET_NAME = 'yjnpartnerscpsr'
DEFAULT_EU_RP = "YJN Europe s.r.o.\n6F, M.R. Stefanika, 010 01, Zilina, Slovak Republic"

# ======================================================================
# 텍스트 줄바꿈 유틸
# ======================================================================
def wrap_text(text, max_width_px, font):
    if not text:
        return []
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = current + (" " if current else "") + w
        try:
            w_px = font.getbbox(test)[2]
        except Exception:
            w_px = len(test) * 7
        if w_px <= max_width_px:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines
# ======================================================================
# 1) Google Vision OCR 호출
# ======================================================================

def upload_to_gcs(storage_client, file_path, bucket_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(os.path.basename(file_path))
    blob.upload_from_filename(file_path)
    return f'gs://{bucket_name}/{os.path.basename(file_path)}'


def call_ocr_api(file_path: str) -> str:
    key_file_path = os.path.join(BASE_DIR, SERVICE_ACCOUNT_FILE)

    try:
        vision_client = vision.ImageAnnotatorClient.from_service_account_json(key_file_path)
        storage_client = storage.Client.from_service_account_json(key_file_path)
    except Exception as e:
        return f"[오류] Google API 초기화 실패: {e}"

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    # -----------------------------
    # 이미지 파일 즉시 OCR
    # -----------------------------
    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"]:
        try:
            with open(file_path, "rb") as f:
                content = f.read()

            image = vision.Image(content=content)
            response = vision_client.document_text_detection(image=image)

            if response.error.message:
                return f"[오류] Vision API 오류: {response.error.message}"

            if response.full_text_annotation.text:
                return response.full_text_annotation.text

            if response.text_annotations:
                return response.text_annotations[0].description

            return "[결과 없음]"
        except Exception as e:
            return f"[오류] 이미지 OCR 실패: {e}"

    # -----------------------------
    # PDF / TIFF → 비동기 OCR
    # -----------------------------
    try:
        gcs_uri = upload_to_gcs(storage_client, file_path, GCS_BUCKET_NAME)
    except Exception as e:
        return f"[오류] GCS 업로드 실패: {e}"

    prefix = f"{os.path.basename(file_path)}_output_{int(time.time())}/"
    destination_uri = f"gs://{GCS_BUCKET_NAME}/{prefix}"

    mime_type = "application/pdf"
    if ext in [".tif", ".tiff"]:
        mime_type = "image/tiff"

    input_config = vision.InputConfig(
        gcs_source=vision.GcsSource(uri=gcs_uri),
        mime_type=mime_type
    )
    output_config = vision.OutputConfig(
        gcs_destination=vision.GcsDestination(uri=destination_uri),
        batch_size=1
    )

    request = vision.AsyncAnnotateFileRequest(
        input_config=input_config,
        features=[vision.Feature(type=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)],
        output_config=output_config
    )

    try:
        operation = vision_client.async_batch_annotate_files(requests=[request])
        operation.result(timeout=600)
    except Exception as e:
        return f"[오류] 비동기 OCR 실패: {e}"

    bucket = storage_client.bucket(GCS_BUCKET_NAME)

    # JSON 결과 합치기
    json_blobs = list(bucket.list_blobs(prefix=prefix))
    json_blobs = [b for b in json_blobs if b.name.endswith(".json")]

    if not json_blobs:
        return "[결과 없음] JSON 결과 없음"

    json_blobs.sort(key=lambda b: b.name)
    full_text = ""

    try:
        for blob in json_blobs:
            text = blob.download_as_bytes().decode("utf-8")
            parsed = json.loads(text)

            for resp in parsed.get("responses", []):
                if "fullTextAnnotation" in resp:
                    full_text += resp["fullTextAnnotation"].get("text", "") + "\n"

    except Exception as e:
        return f"[오류] JSON 파싱 오류: {e}"
    finally:
        # 결과 파일 정리
        try:
            for blob in json_blobs:
                blob.delete()
            bucket.blob(os.path.basename(file_path)).delete()
        except Exception:
            pass

    return full_text.strip() if full_text.strip() else "[결과 없음]"


# ======================================================================
# 2) OCR Parsing
# ======================================================================

def _clean_field_text(text):
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(
        r'^(Product\s*Name|판매명|제품명|Description|Claim/Function|Function|Marketing\s*Claim/Function|Marketing\s*Claim|How\s*to\s*use|Warning|Responsible\s*Person|Ingredients|Net\s*Content)[:\-\s]+\s*',
        "",
        t,
        flags=re.IGNORECASE
    )
    return t.strip()


def _extract_field(start_pattern, end_pattern, text):
    regex = r"(" + start_pattern + r")\s*[:=\-\s]*(.*?)(?=\s*" + end_pattern + r"|\Z)"
    m = re.search(regex, text, re.IGNORECASE | re.DOTALL)
    return _clean_field_text(m.group(2)) if m else None


def parse_ocr_text_to_data(ocr_text: str) -> Dict[str, Any]:

    if ocr_text.startswith(("[오류]", "[결과 없음]")):
        return {"Error": ocr_text}

    cleaned = re.sub(r"[\r\n]+", " ", ocr_text)

    # CPSR Section 분리
    m_section = re.search(
        r"Labelled warnings and instructions of use(.*?)(Reasoning|Assessor|Annex|\Z)",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL
    )
    section = m_section.group(1).strip() if m_section else cleaned

    data = {
        "Product Name": _extract_field(r"Label\w* Information", r"Description", section),
        "Description": _extract_field(r"Description", r"Marketing", section),
        "Function/Claim": _extract_field(r"Marketing", r"How to use", section),
        "Usage / Instructions": _extract_field(r"How to use", r"Warning", section),
        "Warnings / Precautions": _extract_field(r"Warning", r"Responsible|Ingredients", section),
        "Responsible Person": _extract_field(r"Responsible", r"Ingredients", section),
        "INCI / Ingredients": _extract_field(r"Ingredients", r"Net Content", section),
        "Net Content": None,
        "Batch / Lot": None,
        "Expiry Date": None,
        "Country of Origin": None,
    }

    # Net Content 세부 필드
    net = _extract_field(r"Net Content", r"Warning|$", section)
    if net:
        # Net Content
        m_nc = re.search(r"(\d+\s*(ml|mL|g|G))", net)
        if m_nc:
            data["Net Content"] = m_nc.group(1)

        # Expiry
        m_exp = re.search(r"Best Before.*?:\s*(.*?)(,|$)", net)
        if m_exp:
            data["Expiry Date"] = m_exp.group(1).strip()

        # LOT
        m_lot = re.search(r"LOT\s*:\s*(.*?)(,|$)", net)
        if m_lot:
            data["Batch / Lot"] = m_lot.group(1).strip()

        # Origin
        m_origin = re.search(r"Origin\s*:\s*(.*?)(,|$)", net)
        if m_origin:
            val = m_origin.group(1).strip()
            val = re.sub(r"\s+\d{1,3}$", "", val)
            data["Country of Origin"] = val

    # fallback product name
    if not data["Product Name"]:
        if "UNICONIC SHIELD FIXER" in cleaned:
            data["Product Name"] = "SELF BEAUTY UNICONIC SHIELD FIXER"

    return data
# ======================================================================
# 3) INCI 기반 자동 경고 생성
# ======================================================================
def generate_auto_warnings_from_inci(inci_text: str) -> str:
    if not inci_text:
        return ""
    s = inci_text.lower()
    warnings = []

    # 대표 알레르겐 예시
    allergens = [
        "limonene", "linalool", "citral", "geraniol", "coumarin",
        "eugenol", "farnesol", "benzyl alcohol", "benzyl salicylate",
        "citronellol", "hexyl cinnamal", "parfum"
    ]
    found = []
    for a in allergens:
        if a in s and a not in found:
            found.append(a)
            warnings.append(f"Contains allergen: {a.capitalize()}.")

    if "alcohol denat" in s:
        warnings.append("Caution: Contains denatured alcohol; may be drying for sensitive skin.")
    if "althaea rosea flower extract" in s:
        warnings.append("Check for floral extract sensitivities.")

    # 기본 어린이 주의 문구
    if "Not to be used for children under three years of age." not in warnings:
        warnings.append("Not to be used for children under three years of age.")

    return "\n".join(warnings) if warnings else "No specific INCI warnings detected."


# ======================================================================
# 4) EU 라벨 텍스트 구성 (1~11번 포맷)
# ======================================================================
def compose_eu_label_text(form_data: Dict[str, str]) -> str:
    lines = []
    lines.append("────────────────────────────────────────────")
    lines.append("              YJN 파트너스 라벨 예시안")
    lines.append("────────────────────────────────────────────\n")

    lines.append("1. Product Name:")
    lines.append(form_data.get("Product Name", "N/A") + "\n")

    lines.append("2. Product Function:")
    lines.append(form_data.get("Function/Claim", "N/A") + "\n")

    lines.append("3. How to Use:")
    lines.append(form_data.get("Usage / Instructions", "N/A") + "\n")

    lines.append("4. Warning / Precautions:")
    lines.append(form_data.get("Warnings / Precautions", "N/A") + "\n")

    lines.append("5. Ingredients (INCI):")
    lines.append(form_data.get("INCI / Ingredients", "N/A") + "\n")

    lines.append("6. Expiry Date:")
    lines.append(form_data.get("Expiry Date", "Shown on the package") + "\n")

    lines.append("7. EU Responsible Person:")
    lines.append(form_data.get("EU Responsible Person", DEFAULT_EU_RP) + "\n")

    lines.append("8. Distributor Name and Address:")
    distributor_val = form_data.get(
        "Distributor",
        "해당국 수입 판매자(DISTRIBUTOR)의 정보 기입은 필수사항입니다."
    )
    lines.append(distributor_val)
    lines.append("※ DT는 필수 기재사항 / Manufacturer 문구는 선택 사항\n")

    lines.append("9. Country of Origin:")
    lines.append(form_data.get("Country of Origin", "Made in Korea") + "\n")

    lines.append("10. Batch Number:")
    lines.append(form_data.get("Batch / Lot", "Shown on the package (LOT 번호 사용가능)") + "\n")

    lines.append("11. Nominal Quantities:")
    lines.append(form_data.get("Net Content", "N/A") + "\n")

    lines.append("────────────────────────────────────────────")
    lines.append("※ 이 라벨 예시는 CPSR Part B를 기반으로 자동 생성된 초안입니다.")
    lines.append("※ 실제 사용 전, EU 규정(EC) 1223/2009 및 각국 라벨링 요건을 다시 검토해야 합니다.")
    lines.append("────────────────────────────────────────────")

    return "\n".join(lines)


# ======================================================================
# 5) 이미지 라벨 생성 (로고 + 1~11번 포맷)
# ======================================================================
def generate_label_image_from_form(form_data: Dict[str, str], save_path: str) -> str:
    W, H = 1000, 1800
    margin = 40
    bg = "white"

    img = Image.new("RGB", (W, H), color=bg)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("malgunbd.ttf", 36)
        font_bold = ImageFont.truetype("malgunbd.ttf", 24)
        font_reg = ImageFont.truetype("malgun.ttf", 22)
    except Exception:
        font_title = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_reg = ImageFont.load_default()

    x = margin
    y = margin

    # -------------------------
    # 상단 로고 (yjn로고.png)
    # -------------------------
    try:
        logo = Image.open("yjn로고.png")
        logo_ratio = W / logo.width
        logo_h = int(logo.height * logo_ratio)
        logo = logo.resize((W, logo_h), Image.LANCZOS)
        img.paste(logo, (0, y))
        y += logo_h + 30
    except Exception as e:
        print("라벨 로고 로딩 실패:", e)
        title = form_data.get("Product Name", "Product Name")
        draw.text((x, y), title, font=font_title, fill="black")
        y += 70

    # 블록 출력 함수
    def write_block(number, label, content, extra_comment=None, gap=28):
        nonlocal y
        draw.text((x, y), f"{number}. {label}", font=font_bold, fill="black")
        y += gap
        for line in wrap_text(content, W - 2 * margin, font_reg):
            draw.text((x, y), line, font=font_reg, fill="black")
            y += gap
        if extra_comment:
            draw.text((x + 20, y), extra_comment, font=font_reg, fill="black")
            y += gap
        y += 12

    # 1~11 항목
    write_block(1, "Product Name:", form_data.get("Product Name", "N/A"))
    write_block(2, "Product Function:", form_data.get("Function/Claim", "N/A"))
    write_block(3, "How to Use:", form_data.get("Usage / Instructions", "N/A"))
    write_block(4, "Warning / Precautions:", form_data.get("Warnings / Precautions", "N/A"))
    write_block(5, "Ingredients (INCI):", form_data.get("INCI / Ingredients", "N/A"))
    write_block(6, "Expiry Date:", form_data.get("Expiry Date", "Shown on the package"))

    write_block(7, "EU Responsible Person:",
                form_data.get("EU Responsible Person", DEFAULT_EU_RP))

    write_block(
        8,
        "Distributor Name and Address:",
        form_data.get("Distributor", "해당국 수입 판매자(DISTRIBUTOR)의 정보 기입은 필수사항입니다."),
        extra_comment="※ DT는 필수 기재사항 / Manufacturer 문구는 선택 사항"
    )

    write_block(9, "Country of Origin:", form_data.get("Country of Origin", "Made in Korea"))

    write_block(
        10,
        "Batch Number:",
        form_data.get("Batch / Lot", "Shown on the package (LOT 번호 사용가능)"),
        extra_comment="(LOT 번호 사용 가능)"
    )

    write_block(11, "Nominal Quantities:", form_data.get("Net Content", "N/A"))

    # 하단 고정 문구
    y = H - 120
    draw.line((margin, y, W - margin, y), fill="black", width=1)
    y += 10

    rp = form_data.get("EU Responsible Person", DEFAULT_EU_RP)
    for line in rp.split("\n"):
        draw.text((x, y), line, font=font_reg, fill="black")
        y += 28

    y += 6
    draw.text(
        (x, y),
        "※ 이 라벨 이미지는 CPSR Part B를 기반으로 자동 생성된 예시안입니다.",
        font=font_reg,
        fill="black",
    )

    img.save(save_path)
    return save_path
# ======================================================================
# 6) GUI (ttkbootstrap + 전체 스크롤 구조)
# ======================================================================
import ttkbootstrap as ttk
from ttkbootstrap.constants import *


class CPSRApp:
    def __init__(self, master):
        self.master = master
        master.title("YJN파트너스 EU 라벨 자동 생성기")

        style = ttk.Style()
        style.configure("Header.TLabel", font=("Helvetica", 12, "bold"))

        self.file_path = tk.StringVar()
        self.last_parsed_data = None

        self.create_widgets()

    # -------------------------
    # 로고 리사이즈용 함수
    # -------------------------
    def update_logo(self):
        if not hasattr(self, "original_logo"):
            return

        # 🔥 canvas 폭 기준
        target_width = self.canvas.winfo_width()

        if target_width < 50:
            self.master.after(100, self.update_logo)
            return

        ratio = target_width / self.original_logo.width
        new_height = int(self.original_logo.height * ratio)

        # 최대 높이 제한
        #max_h = 150
        #if new_height > max_h:
            #new_height = max_h
            #target_width = int(self.original_logo.width * (max_h / self.original_logo.height))

        resized = self.original_logo.resize((target_width, new_height), Image.LANCZOS)
        self.logo_photo = ImageTk.PhotoImage(resized)

        self.logo_label.configure(image=self.logo_photo)
        self.logo_label.image = self.logo_photo





    # -------------------------
    # 위젯 구성
    # -------------------------
    def create_widgets(self):
        # 0) 전체 스크롤 가능한 Canvas + Frame
        # Canvas 생성
        self.canvas = tk.Canvas(self.master, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(self.master, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 스크롤 프레임 생성
        self.scrollable_frame = ttk.Frame(self.canvas)

        # 🔥 window_id 저장 필수
        self.window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # scrollregion 업데이트
        def update_scrollregion(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.scrollable_frame.bind("<Configure>", update_scrollregion)

        # 🔥 Canvas 크기 변화 시 scrollable_frame 폭 강제 확장
        def resize_frame(event):
            self.canvas.itemconfig(self.window_id, width=event.width)

        self.canvas.bind("<Configure>", resize_frame)



        # 1) 상단 로고
        # -------------------------------
# 0) 상단 회사 로고 (스크롤 영역 안으로 이동)
# -------------------------------
        try:
            logo_path = "yjn로고.png"
            self.original_logo = Image.open(logo_path)

            # 로고는 scrollable_frame 안에 있어야 자동 리사이즈됨
            self.logo_frame = ttk.Frame(self.scrollable_frame)
            self.logo_frame.pack(fill='x')

            self.logo_label = ttk.Label(self.logo_frame)
            self.logo_label.pack(fill='x')

            # 최초 표시 (너무 빨리 실행되면 width가 1이므로 약간 지연)
            self.master.after(200, self.update_logo)

            # 창 변화 감지
            self.master.bind("<Configure>", lambda e: self.master.after(50, self.update_logo))

        except Exception as e:
            print("로고 로딩 실패:", e)

        # 2) 파일 선택 / 버튼 영역
        top_frame = ttk.Frame(self.scrollable_frame, padding=10)
        top_frame.pack(fill='x')

        ttk.Label(top_frame, text="1. CPSR Part B 파일 선택", style="Header.TLabel").pack(anchor='w', pady=3)

        file_entry = ttk.Entry(top_frame, textvariable=self.file_path, state='readonly', width=90)
        file_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        select_button = ttk.Button(top_frame, text="파일 선택", command=self.select_file)
        select_button.pack(side='left')

        process_button = ttk.Button(top_frame, text="OCR 분석 시작", command=self.process_file)
        process_button.pack(side='left', padx=8)

        gen_button = ttk.Button(top_frame, text="이미지 라벨 저장하기", command=self.on_generate_label)
        gen_button.pack(side='right')

        # 3) 입력 폼 영역
        form_frame = ttk.Labelframe(self.scrollable_frame, text="(수정 가능)", padding=10)
        form_frame.pack(fill='x', padx=10, pady=8, expand=False)

        form_frame.columnconfigure(1, weight=1)  # 오른쪽 컬럼 확장

        lbl_w = 18
        ttk.Label(form_frame, text="Product Name:", width=lbl_w).grid(row=0, column=0, sticky='nw', pady=4)
        self.entry_name = ttk.Entry(form_frame, width=80)
        self.entry_name.grid(row=0, column=1, sticky='we', pady=4)

        ttk.Label(form_frame, text="Product Function:", width=lbl_w).grid(row=1, column=0, sticky='nw', pady=4)
        self.entry_function = ttk.Entry(form_frame, width=80)
        self.entry_function.grid(row=1, column=1, sticky='we', pady=4)

        ttk.Label(form_frame, text="How to Use:", width=lbl_w).grid(row=2, column=0, sticky='nw', pady=4)
        self.txt_usage = scrolledtext.ScrolledText(form_frame, width=60, height=3, wrap=tk.WORD)
        self.txt_usage.grid(row=2, column=1, sticky='we', pady=4)

        ttk.Label(form_frame, text="Warnings / Precautions:", width=lbl_w).grid(row=3, column=0, sticky='nw', pady=4)
        self.txt_warnings = scrolledtext.ScrolledText(form_frame, width=60, height=3, wrap=tk.WORD)
        self.txt_warnings.grid(row=3, column=1, sticky='we', pady=4)

        ttk.Label(form_frame, text="Ingredients (INCI):", width=lbl_w).grid(row=4, column=0, sticky='nw', pady=4)
        self.txt_inci = scrolledtext.ScrolledText(form_frame, width=60, height=4, wrap=tk.WORD)
        self.txt_inci.grid(row=4, column=1, sticky='we', pady=4)

        ttk.Label(form_frame, text="Distributor (DT):", width=lbl_w).grid(row=5, column=0, sticky='nw', pady=4)
        self.entry_distributor = ttk.Entry(form_frame, width=80)
        self.entry_distributor.grid(row=5, column=1, sticky='we', pady=4)
        self.entry_distributor.insert(0, "해당국 수입 판매자(DISTRIBUTOR)의 정보 기입은 필수사항입니다.")

        ttk.Label(form_frame, text="Manufacturer:", width=lbl_w).grid(row=6, column=0, sticky='nw', pady=4)
        self.entry_manufacturer = ttk.Entry(form_frame, width=80)
        self.entry_manufacturer.grid(row=6, column=1, sticky='we', pady=4)
        self.entry_manufacturer.insert(0, "제조업자(MANUFACTURER)의 정보 기입은 선택사항입니다.")

        ttk.Label(form_frame, text="EU Responsible Person:", width=lbl_w).grid(row=7, column=0, sticky='nw', pady=4)
        self.txt_rp = scrolledtext.ScrolledText(form_frame, width=60, height=3, wrap=tk.WORD)
        self.txt_rp.grid(row=7, column=1, sticky='we', pady=4)
        self.txt_rp.delete('1.0', tk.END)
        self.txt_rp.insert('1.0', DEFAULT_EU_RP)

        ttk.Label(form_frame, text="Country of Origin:", width=lbl_w).grid(row=8, column=0, sticky='nw', pady=4)
        self.entry_origin = ttk.Entry(form_frame, width=40)
        self.entry_origin.grid(row=8, column=1, sticky='w', pady=4)
        self.entry_origin.insert(0, "Made in Korea")

        ttk.Label(form_frame, text="Batch / Lot:", width=lbl_w).grid(row=9, column=0, sticky='nw', pady=4)
        self.entry_batch = ttk.Entry(form_frame, width=40)
        self.entry_batch.grid(row=9, column=1, sticky='w', pady=4)
        self.entry_batch.insert(0, "Shown on the package (LOT 번호 사용가능)")

        ttk.Label(form_frame, text="Nominal Quantity:", width=lbl_w).grid(row=10, column=0, sticky='nw', pady=4)
        self.entry_nominal = ttk.Entry(form_frame, width=40)
        self.entry_nominal.grid(row=10, column=1, sticky='w', pady=4)

        ttk.Label(form_frame, text="Expiry (파일에 있다면):", width=lbl_w).grid(row=11, column=0, sticky='nw', pady=4)
        self.entry_expiry = ttk.Entry(form_frame, width=40)
        self.entry_expiry.grid(row=11, column=1, sticky='w', pady=4)

        # 4) Notebook 탭 (분석 요약 / 원본 텍스트 / EU 라벨 예시)
        main_frame = ttk.Frame(self.scrollable_frame, padding=10)
        main_frame.pack(fill='both', expand=True)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)

        summary_tab = ttk.Frame(self.notebook)
        self.notebook.add(summary_tab, text='분석 요약')
        self.summary_text = scrolledtext.ScrolledText(summary_tab, wrap=tk.WORD, font=("Helvetica", 11))
        self.summary_text.pack(fill='both', expand=True)

        raw_tab = ttk.Frame(self.notebook)
        self.notebook.add(raw_tab, text='원본 파일 텍스트')
        self.raw_text = scrolledtext.ScrolledText(raw_tab, wrap=tk.WORD, font=("Consolas", 10))
        self.raw_text.pack(fill='both', expand=True)

        eu_tab = ttk.Frame(self.notebook)
        self.notebook.add(eu_tab, text='EU 라벨 텍스트')
        self.text_eu = scrolledtext.ScrolledText(eu_tab, wrap=tk.WORD, font=("Helvetica", 11))
        self.text_eu.pack(fill='both', expand=True)

    # -------------------------
    # 파일 선택
    # -------------------------
    def select_file(self):
        filetypes = [("이미지/PDF 파일", "*.pdf *.jpg *.jpeg *.png *.tif *.tiff"), ("모든 파일", "*.*")]
        path = filedialog.asksaveasfilename if False else filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.file_path.set(path)
            msg = f"파일 선택: {os.path.basename(path)}\n'OCR 분석 시작'을 눌러주세요."
            self.summary_text.delete('1.0', tk.END)
            self.summary_text.insert('1.0', msg)

    # -------------------------
    # OCR → 파싱 → 폼 채우기
    # -------------------------
    def process_file(self):
        file_path = self.file_path.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("오류", "CPSR 파일을 먼저 선택해주세요.")
            return

        self.summary_text.delete('1.0', tk.END)
        self.summary_text.insert('1.0', "OCR 분석 중... 잠시 기다려주세요.")
        self.raw_text.delete('1.0', tk.END)
        self.raw_text.insert('1.0', "API 호출 중...")

        ocr_text = call_ocr_api(file_path)
        if ocr_text.startswith(("[오류]", "[결과 없음]")):
            messagebox.showerror("OCR/인증 오류", ocr_text)
            self.summary_text.delete('1.0', tk.END)
            self.summary_text.insert('1.0', ocr_text)
            self.raw_text.delete('1.0', tk.END)
            self.raw_text.insert('1.0', ocr_text)
            return

        parsed = parse_ocr_text_to_data(ocr_text)
        self.last_parsed_data = parsed

        widgets_to_fill = {
            "Product Name": self.entry_name,
            "Function/Claim": self.entry_function,
            "Usage / Instructions": self.txt_usage,
            "Warnings / Precautions": self.txt_warnings,
            "INCI / Ingredients": self.txt_inci,
            "Net Content": self.entry_nominal,
            "Expiry Date": self.entry_expiry,
        }

        for key, widget in widgets_to_fill.items():
            value = parsed.get(key)
            if value:
                if isinstance(widget, tk.Entry):
                    widget.delete(0, tk.END)
                    widget.insert(0, value)
                elif isinstance(widget, scrolledtext.ScrolledText):
                    widget.delete('1.0', tk.END)
                    widget.insert('1.0', value)

        # RP
        if parsed.get("Responsible Person"):
            self.txt_rp.delete('1.0', tk.END)
            self.txt_rp.insert('1.0', parsed.get("Responsible Person"))
        else:
            self.txt_rp.delete('1.0', tk.END)
            self.txt_rp.insert('1.0', DEFAULT_EU_RP)

        # Origin
        if parsed.get("Country of Origin"):
            self.entry_origin.delete(0, tk.END)
            self.entry_origin.insert(0, parsed.get("Country of Origin"))
        else:
            self.entry_origin.delete(0, tk.END)
            self.entry_origin.insert(0, "Made in Korea")

        # 요약
        summary = (
            f"제품명: {parsed.get('Product Name')}\n"
            f"기능: {parsed.get('Function/Claim')}\n\n"
            f"전성분(INCI):\n{parsed.get('INCI / Ingredients')}\n\n"
            f"경고(추출):\n{parsed.get('Warnings / Precautions')}\n\n"
        )
        auto_warn = generate_auto_warnings_from_inci(parsed.get("INCI / Ingredients", ""))
        summary += f"자동 경고 (INCI 기반):\n{auto_warn}\n"

        self.summary_text.delete('1.0', tk.END)
        self.summary_text.insert('1.0', summary)
        self.raw_text.delete('1.0', tk.END)
        self.raw_text.insert('1.0', ocr_text)

        # EU 라벨 텍스트 미리보기 (현재 폼 값 기반)
        form_data = {
            "Product Name": self.entry_name.get().strip(),
            "Function/Claim": self.entry_function.get().strip(),
            "Usage / Instructions": self.txt_usage.get('1.0', tk.END).strip(),
            "Warnings / Precautions": self.txt_warnings.get('1.0', tk.END).strip(),
            "INCI / Ingredients": self.txt_inci.get('1.0', tk.END).strip(),
            "Distributor": self.entry_distributor.get().strip(),
            "EU Responsible Person": self.txt_rp.get('1.0', tk.END).strip(),
            "Country of Origin": self.entry_origin.get().strip() or "Made in Korea",
            "Batch / Lot": self.entry_batch.get().strip() or "Shown on the package (LOT 번호 사용가능)",
            "Expiry Date": self.entry_expiry.get().strip() or "Shown on the package",
            "Net Content": self.entry_nominal.get().strip() or "",
        }
        eu_text = compose_eu_label_text(form_data)
        self.text_eu.delete('1.0', tk.END)
        self.text_eu.insert('1.0', eu_text)

        messagebox.showinfo(
            "완료",
            "OCR 분석 및 폼 자동채우기가 완료되었습니다.\n필요시 폼을 수정한 뒤 '이미지 라벨 저장하기'를 클릭하세요."
        )

    # -------------------------
    # 라벨 이미지 생성 버튼
    # -------------------------
    def on_generate_label(self):
        form_data = {
            "Product Name": self.entry_name.get().strip(),
            "Function/Claim": self.entry_function.get().strip(),
            "Usage / Instructions": self.txt_usage.get('1.0', tk.END).strip(),
            "Warnings / Precautions": self.txt_warnings.get('1.0', tk.END).strip(),
            "INCI / Ingredients": self.txt_inci.get('1.0', tk.END).strip(),
            "Manufacturer / 제조·판매업자": self.entry_manufacturer.get().strip(),
            "Distributor": self.entry_distributor.get().strip(),
            "EU Responsible Person": self.txt_rp.get('1.0', tk.END).strip(),
            "Country of Origin": self.entry_origin.get().strip() or "Made in Korea",
            "Batch / Lot": self.entry_batch.get().strip() or "Shown on the package (LOT 번호 사용가능)",
            "Expiry Date": self.entry_expiry.get().strip() or "Shown on the package",
            "Net Content": self.entry_nominal.get().strip() or ""
        }

        initialfile = (form_data.get("Product Name") or "label_example").replace(" ", "_").replace("/", "_") + ".png"
        save_path = filedialog.asksaveasfilename(
            defaultextension='.png',
            filetypes=[("PNG 이미지", "*.png")],
            initialfile=initialfile
        )
        if not save_path:
            return

        try:
            saved = generate_label_image_from_form(form_data, save_path)
            messagebox.showinfo("저장 완료", f"예시 라벨 파일을 저장했습니다:\n{saved}")
        except Exception as e:
            messagebox.showerror("라벨 생성 실패", f"라벨 생성 중 오류가 발생했습니다: {e}")
# ======================================================================
# 창 크기 저장/로드
# ======================================================================
def save_window_geometry(root):
    try:
        with open("window_size.cfg", "w", encoding="utf-8") as f:
            f.write(root.geometry())
    except Exception:
        pass


def load_window_geometry():
    if os.path.exists("window_size.cfg"):
        try:
            with open("window_size.cfg", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None
    return None


# ======================================================================
# 실행부
# ======================================================================
if __name__ == "__main__":
    root = ttk.Window(themename="flatly")  # flatly / minty / cosmo 등 선택 가능
    root.iconbitmap("yjn작업표시줄아이콘.ico")
    last_geometry = load_window_geometry()
    if last_geometry:
        root.geometry(last_geometry)
    else:
        root.after(50, lambda: root.state('zoomed'))  # 첫 실행은 화면 꽉 차게

    root.resizable(True, True)

    app = CPSRApp(root)

    def on_closing():
        save_window_geometry(root)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

## ��õ ���� �帧 (Cloud Run + Vercel)

### 1) GCP Cloud Run (�鿣��)
1. GCP ������Ʈ ����/����
2. API Ȱ��ȭ
   - Cloud Run
   - Artifact Registry
   - Cloud Build
   - Vision API
   - Cloud Storage
3. ���� ������ ���� �ο�
   - Vision API ���
   - Storage Object Admin (OCR PDF/TIFF ó�� �� �ʿ�)

### 2) ��� & ���� (Cloud Run)
PowerShell ����:

```
# �α���
 gcloud auth login
 gcloud config set project YOUR_PROJECT_ID

# ���
 gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/cpsr-label

# ����
 gcloud run deploy cpsr-label \
   --image gcr.io/YOUR_PROJECT_ID/cpsr-label \
   --platform managed \
   --region asia-northeast3 \
   --allow-unauthenticated \
   --set-env-vars GCS_BUCKET_NAME=YOUR_BUCKET_NAME
```

����: `service-account-key.json`�� ��� �̹����� ���Ե˴ϴ�. ������� Secret Manager�� ��ü�ϴ� ���� �����մϴ�.

### 3) Vercel (����Ʈ)
- Vercel���� �� ������Ʈ ����
- ��Ʈ ���� ���� �� ����
- `web/frontend`�� ���� ��Ʈ�� �����˴ϴ� (`vercel.json` ����)

���� �� ����Ʈ���� API Base URL�� Cloud Run URL �Է�

### 4) � üũ����Ʈ
- CORS ������ ���� (�ʿ� ��)
- PDF ��� Ȯ��
- OCR �Է� ���� ���� Ȯ��


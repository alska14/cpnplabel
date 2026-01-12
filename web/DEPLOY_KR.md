## 추천 배포 흐름 (Cloud Run + Vercel)

### 1) GCP Cloud Run (백엔드)
1. GCP 프로젝트 선택/생성
2. API 활성화
   - Cloud Run
   - Artifact Registry
   - Cloud Build
   - Vision API
   - Cloud Storage
3. 서비스 계정에 권한 부여
   - Vision API 사용
   - Storage Object Admin (OCR PDF/TIFF 처리 시 필요)

### 2) 빌드 & 배포 (Cloud Run)
PowerShell 기준:

```
# 로그인
 gcloud auth login
 gcloud config set project YOUR_PROJECT_ID

# 빌드
 gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/cpsr-label

# 배포
 gcloud run deploy cpsr-label \
   --image gcr.io/YOUR_PROJECT_ID/cpsr-label \
   --platform managed \
   --region asia-northeast3 \
   --allow-unauthenticated \
   --set-env-vars GCS_BUCKET_NAME=YOUR_BUCKET_NAME
```

주의: `service-account-key.json`은 빌드 이미지에 포함됩니다. 운영에서는 Secret Manager로 대체하는 것이 안전합니다.

### 3) Vercel (프론트)
- Vercel에서 새 프로젝트 생성
- 루트 폴더 선택 후 배포
- `web/frontend`가 정적 루트로 설정됩니다 (`vercel.json` 포함)

배포 후 프론트에서 API Base URL에 Cloud Run URL 입력

### 4) 운영 체크리스트
- CORS 도메인 제한 (필요 시)
- PDF 출력 확인
- OCR 입력 파일 유형 확인

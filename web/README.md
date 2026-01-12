# CPSR Label Web

This is a lightweight web version of the CPSR label tool.

## Structure
- web/backend: FastAPI + Google Vision OCR + PDF generator
- web/frontend: Static HTML/CSS/JS UI

## Backend setup (local)
1. Create a virtual environment.
2. Install dependencies:
   pip install -r web/backend/requirements.txt
3. Copy env example:
   copy web\backend\.env.example web\backend\.env
4. Set values in `.env`:
   - GCS_BUCKET_NAME
   - GOOGLE_APPLICATION_CREDENTIALS (path to service-account-key.json)
5. Run server:
   uvicorn web.backend.app:app --reload

## Frontend setup (local)
Open `web/frontend/index.html` in a browser and set API Base URL to the backend URL.

## Deployment suggestion
- Backend: Google Cloud Run (keep the service account file server-side only)
- Frontend: Vercel or Firebase Hosting

## Notes
- OCR supports PDF and image files.
- PDF output is text-selectable.

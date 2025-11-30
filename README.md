# Community Savings & Fund Management Platform (Starter)

This repository is a **starter** implementation for the Community Savings & Fund Management Platform described by the user. It contains a Django REST backend and a minimal React frontend scaffold with key features implemented as proof-of-concept: RBAC, Argon2 password hashing, AES encryption for sensitive fields, audit logging, JWT auth, QR token flow, file upload restrictions, and reserve/liquid buckets with FIFO withdrawal rules.

> This is a starter app — not a production-ready complete banking system. It demonstrates architecture, key models, APIs, and frontend interactions so you can inspect, extend, and deploy.

## What’s included
- `backend/` — Django project with apps: `users`, `funds`, `stores`
- `frontend/` — Minimal React app (create-react-app-style) with example pages
- `docs/` — Short notes about security & running locally
- `requirements.txt` — Python requirements for backend
- `community_savings_platform.zip` — Zipped package of this project root (created by this script)

## How to run locally (backend)
1. Install Python 3.10+ and Node 18+.
2. Create and activate a virtualenv:
```bash
python -m venv venv
source venv/bin/activate   # macOS / Linux
```
3. Install requirements:
```bash
pip install -r requirements.txt
```
4. Run migrations and create superuser:
```bash
cd backend
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```
5. Run the dev server:
```bash
python manage.py runserver
```
6. API root will be at `http://127.0.0.1:8000/api/`

## How to run locally (frontend)
1. `cd frontend`
2. `npm install`
3. `npm start` — runs React dev server on port 3000 by default and talks to backend APIs.

## Notes & Next steps
- MFA flows are scaffolded with placeholders; integrate an MFA provider (e.g. TOTP).
- File uploads stored to local filesystem; for production use cloud storage with virus scan hooks.
- Encryption uses Fernet symmetric keys in settings; keep keys secure and use HSM/KMS in prod.
- Audit log is immutable at model level; consider append-only log stores for stronger guarantees.
- Many business rules are implemented in models and serializers as examples (reserve FIFO logic).

If you want, I can extend specific parts (complete frontend flows, add tests, Dockerfile, CI, or integrate payment rails).

# Satawo

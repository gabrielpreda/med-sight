# Deployment & Cleanup Summary

## Changes Made
1. **Cleanup**: Removed the legacy `app.py` from the root directory to avoid confusion. The active application logic resides in `src/ui/app.py`.
2. **Configuration Updates**:
    - **`app.yaml`**: Updated the Google App Engine entrypoint to point directly to `src/ui/app.py`.
    - **`run_app.py`**: Verified it correctly imports from `src/ui/app.py`, so local execution via `python run_app.py` or `start.sh` continues to work.
3. **New Deployment Assets**:
    - **`Dockerfile`**: Created a production-ready Dockerfile based on `python:3.10-slim`. It cleans up apt lists and copies requirements first for caching.
    - **`.dockerignore`**: Added to exclude unnecessary files like virtual envs and git helpers from the build context.

## How to Deploy
### Option 1: Docker / Cloud Run
```bash
# Build the container
docker build -t medsight .

# Run locally
docker run -p 8080:8080 medsight --env-file .env
```

### Option 2: App Engine
```bash
gcloud app deploy
```

### Option 3: Local Development
```bash
./start.sh
# OR
streamlit run src/ui/app.py
```

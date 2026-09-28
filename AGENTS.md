# Base44 Dev Environment

## Project Overview
Flask web app for concrete crack detection using OpenCV + NumPy + SciPy. Users upload or capture images; the app analyzes cracks, estimates dimensions, and classifies severity.

## Setup
- Source was originally in `concrete_crack_detection_large_structure.zip`; extracted to repo root.
- Runs via `docker compose -f docker-compose.base44.yml up -d`.
- App listens on port 5000 inside the container, mapped to host port 3000.
- Base image: `python:3.12-slim`. System deps `libgl1` and `libglib2.0-0` are installed at container startup (required by opencv-python).
- Dependencies from `requirements.txt` are installed at each container start (pip install in the command).
- Flask runs in debug mode with auto-reload, so source edits appear live without rebuilding.

## Secrets
- `FLASK_SECRET_KEY` — required at boot; a development placeholder is auto-generated. Replace with a real value for production use.

## Health
- Healthcheck: `GET /` on port 5000 inside the container.
- Verify: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/` should return 200.

## No External Services
- No database, cache, or external API dependencies. Uploaded images and results are stored on the local filesystem (`uploads/` and `outputs/` directories).

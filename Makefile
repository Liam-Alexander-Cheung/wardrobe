# make setup   one-time: Python venv + packages, frontend build
# make run     your wardrobe on http://127.0.0.1:8766 (data in ~/WardrobeData)
# make demo    12 drawn garments, nothing saved
# make test    backend + frontend tests

PY := .venv/bin/python

.PHONY: setup run demo test test-slow dev

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e .
	cd frontend && npm ci && npm run build

run:
	$(PY) -m wardrobe

demo:
	$(PY) -m wardrobe --demo

test:
	$(PY) -m pytest -q
	cd frontend && npm test

test-slow:  ## also runs the real rembg model (downloads ~170 MB once)
	$(PY) -m pytest -q -m slow

dev:  ## frontend with hot reload on :5173 (run `make run` in another terminal)
	cd frontend && npm run dev

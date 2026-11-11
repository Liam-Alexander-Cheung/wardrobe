"""
Start the app:

    .venv/bin/python -m wardrobe          your wardrobe, data in ~/WardrobeData (or $WARDROBE_DATA)
    .venv/bin/python -m wardrobe --demo   12 drawn garments in a temp folder, nothing saved

Then open http://127.0.0.1:8766
"""

import sys

import uvicorn

from . import config, demo
from .app import create_app

if __name__ == "__main__":
    is_demo = "--demo" in sys.argv[1:]
    if is_demo:
        root = demo.temp_dir()
        demo.seed(root)
        print(f"Demo mode: drawn garments in {root} (temporary)")
    else:
        root = config.data_dir()
        root.mkdir(parents=True, exist_ok=True)
        print(f"GuardTheRobes data: {root}  (private, outside the repo)")
    print(f"Open http://{config.HOST}:{config.PORT}")
    uvicorn.run(create_app(root, demo=is_demo), host=config.HOST, port=config.PORT, log_level="warning")

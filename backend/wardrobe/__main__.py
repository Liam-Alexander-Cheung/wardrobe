"""Start the app:  .venv/bin/python -m wardrobe   →  http://127.0.0.1:8766"""

import uvicorn

from . import config
from .app import create_app

if __name__ == "__main__":
    root = config.data_dir()
    print(f"Wardrobe data: {root}  (private, outside the repo)")
    print(f"Open http://{config.HOST}:{config.PORT}")
    uvicorn.run(create_app(root), host=config.HOST, port=config.PORT, log_level="warning")

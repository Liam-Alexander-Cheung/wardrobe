"""
Where things live, and the one rule that keeps the public repo clean:
your wardrobe data (photos + database) must sit OUTSIDE the git repository.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
PORT = int(os.environ.get("WARDROBE_PORT", "8766"))
VITE_PORT = 5173  # the frontend dev server (npm run dev), allowed to call the API


class UnsafeDataDir(RuntimeError):
    """The data folder would end up inside the public repo."""


def check_outside_repo(path: Path) -> Path:
    path = Path(path).expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise UnsafeDataDir(
            f"{path} is inside the git repo ({REPO_ROOT}). Your clothes would be one "
            f"`git add` away from GitHub. Pick a folder outside it (default ~/WardrobeData)."
        )
    return path


def data_dir() -> Path:
    """WARDROBE_DATA if set, else ~/WardrobeData. Always outside the repo."""
    return check_outside_repo(Path(os.environ.get("WARDROBE_DATA", Path.home() / "WardrobeData")))

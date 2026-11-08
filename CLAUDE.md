# Wardrobe: notes for Claude

Local-first digital wardrobe. Public repo; the owner's clothes are private.

## Hard rules
- Real wardrobe data lives in `~/WardrobeData` (or `$WARDROBE_DATA`), never in this repo.
  Never copy photos, the database or anything derived from them (screenshots of real
  items included) into the repo. README screenshots come from `make demo` only.
- Owner pushes. Claude branches, commits, and writes PR-style descriptions.
- Tests first for every feature (pytest in `backend/tests`, vitest in `frontend/src/__tests__`).
  `make test` must be green before a commit.

## Map
- `backend/wardrobe/db.py`: the only place that knows the SQLite schema (API + MCP share it)
- `backend/wardrobe/models.py`: validation for both the API and the MCP tools
- `backend/wardrobe/layout.py` ↔ `frontend/src/Board.tsx` HOME: keep the default positions in sync
- `backend/wardrobe/ask.py`: the `claude -p` command line is security-relevant (tool lockdown);
  `test_command_is_locked_down` guards it

## Run
`make run` (real data) · `make demo` (drawn garments, temp folder) · `make dev` (Vite on :5173)

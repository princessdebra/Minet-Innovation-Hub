# Minet Innovation Hub (proof of concept)

React + FastAPI + MySQL. Runs locally, same pattern as the other Minet local stacks.
All content is illustrative dummy data. There is no login: the app runs as one mock user (Alex Mwangi) who can do everything.

## Requirements
- Python 3.11 or newer
- Node 20 or newer
- MySQL 9.7 running locally (8.x also works)

## First run (Windows)
1. **Backend**
   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env          (then put your MySQL password in .env)
   python init_db.py               (creates the innovation_hub database, tables and dummy data)
   uvicorn app.main:app --reload --port 8000
   ```
2. **Frontend** (second terminal)
   ```
   cd frontend
   npm install
   npm run dev
   ```
3. Open http://localhost:5173

`start-backend.bat` and `start-frontend.bat` do the same steps.

## Everyday commands
| Task | Command (in `backend`) |
|---|---|
| Reset the dummy data to the original state | `python init_db.py --reset` |
| Run API smoke tests | `pytest -q` (needs the database seeded) |
| API docs | http://localhost:8000/docs |
| Regenerate `schema.sql` | `python export_schema.py` |

The tests add and remove a few rows. Run `python init_db.py --reset` afterwards if you want a clean demo.

## What is in the POC
Six screens matching the wireframe, plus the pages the wireframe did not design.

| Screen | What works |
|---|---|
| Home | Personal dashboard from the database, Learning and Ideas submitted leaderboard tabs, links to every area |
| Full leaderboard (`/leaderboard`) | Both rankings, your row highlighted |
| Explore challenges | Search plus Source, Horizon and Innovation type filters, empty state |
| Challenge detail (`/explore/:id`) | Background, success, your linked ideas, "Submit an idea for this challenge" |
| Submit an idea | Validation, save draft, resume draft, submit, reference ID, linked challenge |
| My ideas & experiments | Open record changes the selected initiative, drafts can be resumed, edit and resubmit when clarification is needed |
| Learn & connect | Continue learning, recommended paths, mentor request (saved), join or leave the community |
| Learning path (`/learn/paths/:id`) | Mark modules complete, progress feeds Home, Learn and the leaderboard |
| Knowledge & impact | Impact matrix; a benefit shows Validated only if evidence, owner and period all exist (backend rule) |
| Knowledge library (`/knowledge/library/:slug`) | Four sections with sample items |
| Help | Short FAQ |

The top search box searches challenges, your ideas and experiments, learning paths and the library.

Wireframe consistency is enforced by the smoke tests: 40% progress, 18 Nov decision, 2 experiments, 3 next actions, Rank 8 on both leaderboards, 86 / 12 / 4 illustrative activity, NOT VALIDATED status.

## Layout
```
backend/   FastAPI app (app/), seed.py, init_db.py, schema.sql, tests/
frontend/  React + TypeScript + Vite (src/pages, src/components, src/styles)
reference/ Wireframe PNGs, Figma CSS export, supplied logo
docs/      POC plan
```

## Database
`innovation_hub` on your local MySQL. Tables are created from `backend/app/models.py`; `backend/schema.sql` is generated DDL for reference.
Settings are in `backend/.env`. MySQL 9 uses `caching_sha2_password`, which PyMySQL handles through the `cryptography` package (already in requirements).

## RBAC later
Nothing is enforced yet, but the seams are in place:
- `users.role` column exists.
- `backend/app/security.py`: `get_current_user` returns the mock user; `ROLE_PERMISSIONS` maps roles to permissions (currently `*` for all). Write routes already call `require_permission("idea:create")` and similar.
- `frontend/src/state/AppContext.tsx`: `can(permission)` is available to hide controls per role.

## Assets and design notes
- Images are placeholders. The Minet logo is `frontend/src/assets/minet-logo.png`; `minet-logo-white.png` is a reversed version made from it for the dark sidebar. Replace it if brand guidelines supply an official one.
- Colours, type and spacing come from the Figma CSS export (see `frontend/src/styles/tokens.css`). Styling is plain CSS (`styles/app.css`) rather than CSS Modules.
- Inter is bundled with the app, so it works offline.
- No em dashes in the interface copy.

## Known limits
- Desktop layout only (designed for 1280 px and wider).
- Submitted ideas are locked; only drafts and "Needs clarification" ideas can be edited.
- Leaderboards count all-time dummy data under the "This quarter" label, as the wireframe does with "Sample rankings".
- Built and tested here against MySQL 8.0. It uses standard SQL and no MySQL 9 specific features, but please run `pytest -q` on your 9.7 instance to confirm.

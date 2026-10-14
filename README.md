# n4mi-dxcc-analyzer

A small self-hosted app that answers one operating question at a glance: **"What do I still need for DXCC on the bands and modes I actually work?"**

It reads the ARRL Logbook of the World (LoTW) **Award Credit Matrix**, which Dan pastes in, and shows:

- entities never credited;
- every band and mode slot still needed in the operating profile (160–6 m with CW, Phone and Digital by default; 2 m and Satellite can be switched on), counted the way LoTW counts them: never-confirmed entities are included and tagged NEW;
- the full band/mode matrix.

It runs LAN-only on a home NAS (FastAPI + SQLite + vanilla HTML/CSS/JS in Docker).

## Status

**Phase 1, Build Step 3: ready to deploy on the UGreen NAS** (Docker, Portainer, port 8086). What exists:

| File | What it does |
|---|---|
| `app/categories.py` | DXCC categories (Mixed, CW, Phone, Digital, one per band) and the operating profile |
| `app/reference.py` | Loads the DXCC entity table, keyed on the ARRL DXCC entity number |
| `app/parser.py` | Reads the matrix from a LoTW paste, `.txt`, `.csv` or `.xlsx` |
| `app/validate.py` | Rejects bad imports; holds suspicious ones (any credit going down) for review |
| `app/analysis.py` | Missing entities, needed slots, totals, what changed between imports |
| `app/marks.py` | Rules for "awaiting credit" / "won't submit" marks |
| `app/status_check.py` | Cross-check against LoTW's Account Status table |
| `app/clublog.py` | Club Log Most Wanted ranking (public, no key), fetched only on request |
| `app/paper.py` | Paper QSL cards not yet credited: what each card would fill |
| `app/db.py` | SQLite storage: imports, credits, marks, paper cards, settings |
| `app/api.py` | Internal endpoints for the app's own pages (not the DXMon contract) |
| `app/main.py` | App setup, `/healthz`, start-up check |
| `app/exports.py` | CSV and workbook exports, including the DX Monitor bridge file |
| `static/` | The web pages: plain HTML, CSS and JavaScript, no build step |
| `app/data/dxcc_entities.csv` | The 402 DXCC entities (340 current), with continent and CQ zone |
| `tools/build_reference.py` | Development only: rebuilds that table from the verified list and AD1C's `cty.csv` |

## Key rules

- **LoTW credit is the authority.** Confirmations that are not yet credited are never counted as credits.
- **Entities are identified by DXCC number**, never by name or prefix. Names differ between sources, and prefixes such as 3Y, HK0 and VP8 cover several entities.
- **Bands and modes are credited separately**, as ARRL does. Band-and-mode combinations are not slots.
- **Deleted entities are excluded** from every count.
- **A failed import changes nothing**, and a suspicious one needs a deliberate "Save anyway".

## Deploying on the NAS (Portainer)

1. In UGOS Files, create the folder `/volume2/docker/n4mi-dxcc-analyzer/data`. It holds the database (`dxcc.db`) and nothing else.
2. Portainer → **Stacks → Add stack → Repository**:
   - Repository URL `https://github.com/N4MI73/n4mi-dxcc-analyzer`, reference `refs/heads/main`, compose path `docker-compose.yml`
   - Authentication off; GitOps auto-updates off; no environment variables (no credentials in Phase 1)
3. Deploy. Check `http://192.168.6.29:8086/healthz` answers `{"status":"ok"}` and `http://192.168.6.29:8086/api/status` shows `"ok":true`.
4. Uptime Kuma: an HTTP monitor on `/healthz` (is the app up?) and a Keyword monitor on `/api/status` for `"ok":true` (is the database readable and the data folder mounted?).

**Updating:** commit and push, then Portainer → the stack → **Pull and redeploy** (`pull_policy: build` rebuilds from the repo).

**If the data folder isn't mounted**, every page shows "Data folder /app/data not found" instead of quietly starting with an empty database. **Losing the folder** costs only history: one fresh LoTW paste restores current credits; import history, pending marks and paper cards would be lost, so copy `dxcc.db` now and then (best with the stack stopped).

## Running locally

```
pip install -r requirements.txt
uvicorn app.main:create_app --factory --port 8086
```

Then open `http://localhost:8086/`. `http://localhost:8086/healthz` answers `{"status":"ok"}`. The database is created in `data/` (set `DATA_DIR` to put it elsewhere).

## Exports

The **Export** button on the list pages offers four files. All follow the operating profile, not a page's temporary filters.

| File | Contents |
|---|---|
| `dxcc_analysis_YYYY-MM-DD.xlsx` | Summary, Missing Entities, Missing Slots, By Band, Matrix, Pending Marks, Paper QSLs |
| `missing_entities.csv` | Never-credited entities with Most Wanted rank, marks and paper cards |
| `missing_slots.csv` | One row per entity with a need (never-confirmed entities flagged in the last column); one column per profile band and mode |
| `no_confirms.csv` | For DX Monitor (optional): a drop-in replacement for its `no_confirms.csv` (`Entity,Prefix`, no byte-order mark). See below. |

### Loading the list into DX Monitor

This is only for operators who also run DX Monitor; the analyzer works fully without it. DX Monitor builds `server/no_confirms.csv` into its Docker image and reads it once at start-up to seed its Trigger Builder picker. Copying the file to a folder on the server and restarting the container therefore has no effect. Instead:

1. Download `no_confirms.csv` from the **Export** menu.
2. In your local DX Monitor repository, replace `server/no_confirms.csv` with the downloaded file.
3. Commit and push the change.
4. In Portainer, open the `dxmon` stack and choose **Pull and redeploy**, so the image is rebuilt with the new file.

DX Monitor's Needed list stays curated by hand; the new file only changes which entities its picker offers.

## DXpeditions from DX Monitor (optional)

If you also run DX Monitor, enter its address in **Settings → DX Monitor** (for example `http://192.168.6.29:8083`), then **Test connection** and **Save**. Leave the address blank to keep every DX Monitor feature off; the analyzer works fully without it.

When it's on:

- **Missing Entities** tags each needed entity that has a DXpedition in DX Monitor's ADXO list: **ON AIR** while it's active, or its start date if it starts within 30 days. **NOT WATCHED** means it isn't on DX Monitor's Watched list. A **DXpeditions first** sort is added.
- The analyzer reads DX Monitor's `/api/adxo` and `/api/watched` (read-only) when Missing Entities opens, if its last try was over 15 minutes ago, or when you press **Refresh**. If DX Monitor doesn't answer, the last list received stays on screen with its time.
- ADXO names entities in its own spelling. The app matches them to DXCC entities by name and a built-in list of known spellings. Any name it can't place is listed in Settings with a suggestion for you to approve, choose another entity, or ignore; nothing is applied without you.
- The **For DX Monitor** export appears in the Export menu.

## Running the tests

Requires Python 3.11 or later.

```
pip install -r requirements-dev.txt
python -m pytest
```

All test data is synthetic. **Real LoTW exports, pastes and the database are never committed**; `.gitignore` excludes them.

## License

MIT. See `LICENSE`.

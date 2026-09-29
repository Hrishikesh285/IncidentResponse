# OpsMemory — Demo Script

This script walks through the three demo incidents to showcase the core Memory OFF → Memory ON → learning → improvement loop.

---

## Prerequisites

1. Docker Compose running (`docker compose up -d`)
2. `.env` filled with `GROQ_API_KEY`, `HINDSIGHT_API_KEY`, `HINDSIGHT_BASE_URL`
3. Seed data generated: `python data/generate_incidents.py`
4. Seed data loaded: `python scripts/seed_memory.py`
5. Server running: `uvicorn app.main:app --reload`
6. Open `http://localhost:8000` in a browser

---

## Step 1 — Run Demo A with Memory OFF

**Goal:** Show that without memory, the diagnosis is generic.

1. In the top-right, verify the stats bar shows **40 memories retained** (from seed).
2. In the "New Incident" panel, click the **demo dropdown** and select **"Demo A — payments-api pool exhausted (SEV1)"**.
3. **Toggle Memory OFF** using the toggle (it should show grey with "Memory OFF").
4. Click **"Analyze Incident"**.
5. Wait for the diagnosis to appear.

**Expected result:**
- Memory banner reads: **"Memory OFF — no history used (generic diagnosis only)"**
- Diagnosis is generic: something like "check connection pool settings" without citing any specific past incident.
- Confidence: `low` or `medium`.
- Right panel (Recalled from Memory): empty.

---

## Step 2 — Run Demo A with Memory ON

**Goal:** Show that with memory, the diagnosis cites a matching past incident.

1. The form should still be filled with Demo A data.
2. **Toggle Memory ON** (blue, "Memory ON").
3. Click **"Analyze Incident"** again.
4. Wait for the diagnosis.

**Expected result:**
- Memory banner reads: **"Memory ON — used N past incidents"** (N = 1–3).
- Diagnosis cites a seeded incident (e.g. `INC-0001`) from the `db_pool_exhaustion` family.
- Recommended steps match the seeded fix: "Increase pool size to 50; restart pods; add alert."
- Confidence: `high`.
- Right panel shows recalled incident cards, with the best match highlighted in blue with a "★ Best Match" badge.
- Match reason explains why the incident was selected.

---

## Step 3 — Resolve Demo A (Learning Step)

**Goal:** Add Demo A's resolution into memory so future incidents benefit.

1. In the "Mark as Resolved" form below the diagnosis:
   - **Root Cause:** `DB connection pool exhausted after traffic spike`
   - **Fix Steps:**
     ```
     Increase pool size to 50; restart payments-api pods; add pool-timeout alert
     ```
   - **Resolution Time:** `22`
2. Click **"Resolve & Learn"**.

**Expected result:**
- A green banner appears: **"🧠 Learned: this incident is now in memory and will help future diagnoses."**
- Stats bar updates: **Memories retained** increases by 1.

---

## Step 4 — Run Demo C (Shows Compounding Memory)

**Goal:** Show that the just-resolved Demo A now appears in recalled memories alongside the seeded incidents.

1. Click the **demo dropdown** and select **"Demo C — order-service pool exhausted (SEV1)"**.
2. Ensure **Memory ON**.
3. Click **"Analyze Incident"**.

**Expected result:**
- Recalled incidents panel shows **multiple matches** — both a seeded incident AND the just-resolved Demo A (`INC-0041` or similar).
- The diagnosis explicitly references both incidents, explaining that the same pool exhaustion pattern was seen on `payments-api` minutes ago.
- Confidence: `high`.
- Recommended steps include the same resolution that worked for Demo A.

This illustrates the compounding value: each resolved incident makes the next diagnosis better.

---

## Step 5 — Optional: Run Demo B (Redis OOM)

1. Load **Demo B — auth-service Redis OOM** from the dropdown.
2. With **Memory ON**, analyze.

**Expected result:**
- Recalled incidents are from the `redis_oom` family in the seed data.
- Diagnosis recommends raising maxmemory, setting eviction policy, and flushing stale keys — matching the seeded fix.

---

## Reset to Start Over

Click the **"↺ Reset Demo"** button in the top bar and confirm the dialog to wipe all incidents and memories, then re-run `python scripts/seed_memory.py`.

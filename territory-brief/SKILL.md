---
name: territory-brief
description: >
  Territory-level intelligence review for a Dynatrace RD or RVP.
  Discovers the exec's full org hierarchy (RDs → AEs → accounts), pulls pipeline health,
  PowerBI consumption, Gong call coverage per AE, and at-risk account signals — then outputs
  a territory health report: AE-level pipeline table, call-coverage gap report (accounts with
  no Gong calls in the period), open commitment roll-up, and consumption risk summary.
  No meeting-prep cards. Designed for QBR cycles, territory planning, and leadership reviews.
  Runs under the claude-work alias (Claude Enterprise). Outputs text (default) or HTML.
argument-hint: '"<exec-name>" [period] [--html|--text] [optional context]'
when_to_use: >
  When an RD or RVP needs a territory-level health view: which AEs are active, where pipeline
  is stacking up, which accounts have no recent Gong call coverage, and what the consumption
  risk posture looks like across the org. Distinct from /exec-brief (which is meeting-prep
  focused). Triggered by: /territory-brief, "territory plan for <name>", "territory review",
  "QBR prep for my territory", "AE health report".
---

# /territory-brief — Territory Health Intelligence Report

Territory view for an RD or RVP. No meeting-prep cards. The anchor metric is **coverage** —
pipeline coverage, consumption coverage, Gong call coverage — surfaced per AE so leadership
can see gaps, at-risk accounts, and where to coach.

Design lineage: `exec-brief` (pre-flight, Phase 0–1, schema patterns, QA gate). Reuses all
exec-brief infrastructure. Phase 2 is a different stream set optimized for territory-wide
rather than meeting-specific coverage. Full Phase 2 implementation is in progress (Phase 1
scaffold only — see `## Implementation status` below).

---

## PORTABILITY & CONFIG

```
CONFIG:
  SF_ORG_ALIAS          = dynatrace-sf
  POWERBI_APP_ID        = ccd98e24-9039-4a7f-bc70-b7bea4e85b59   (Dynatrace ONE)
  PBI_EXTRACTOR         = ~/.claude/skills/dt-rd-review/scripts/pbi-extract.py
  PBI_MCP_TOOL          = mcp__powerBI__dynatrace_one_grid
  LOGO_PNG              = ~/dt_deck_assets/logo_white_wordmark_v6.png
  OUTPUT_DIR            = current working directory
  SHARED_REFERENCE      = ~/.claude/skills/dt-customer-review/references/account-intel-shared.md
  MAX_AE_GONG_ACCOUNTS  = 50         # per-AE account cap for Gong gap report
  GONG_MAX_CALLS        = 20         # slightly higher than exec-brief; territory is wider
```

---

## Usage

```
/territory-brief "Nishant Rama"
/territory-brief "Nishant Rama" 4w --html
/territory-brief "Nishant Rama" 2w focus on at-risk renewals in the enterprise segment
/territory-brief "Dom Miller" last quarter --html
```

---

## Implementation status

**Phase 1 scaffold** — fully specified through Phase 1 (org discovery). Phase 2 streams,
Phase 3 synthesis, Phase 4 QA, and Phase 5 output are summary-level. Full Phase 2 spec is
a follow-on PR after team review.

---

## Phase -1 — MCP Pre-flight Check (ALWAYS FIRST)

Same as `/exec-brief` Phase -1. Required: Salesforce, Salesforce-auth, PowerBI, M365 connector,
Slack connector. Optional: LinkedIn (webfetch fallback), SuccessFactors (hierarchy fallback),
Gong (call coverage report — degrades gracefully to "Gong not connected").

**If any MCP is missing, auto-install from se-mcp-servers:**
```
Clone https://github.com/clabrado/se-mcp-servers (public) and say "set up <mcp-name>".
```

Pre-flight table format identical to exec-brief Phase -1. Gate: STOP if any required MCP
is missing; DEGRADED on optionals only → proceed.

---

## Phase 0 — Parse Arguments & Initialize

### Arguments

1. **`$EXEC_NAME`** (required) — primary key. Never assume from context.
2. **`$PERIOD`** (optional, default `4w` — wider than exec-brief default):

| Form | Example |
|---|---|
| Shorthand | `2w` `4w` `1q` |
| Words | `last quarter`, `last month` |
| ISO range | `2026-07-01:2026-09-30` |

3. **Output flag** — `--html` | `--text`. Default `--text`. (No `--pdf` for territory-brief.)
4. **`$FOCUS_CONTEXT`** — all remaining freeform text. Injected into scoring and synthesis.

### Derived values

```
PERIOD_DAYS      = normalized integer
WINDOW_START     = now − PERIOD_DAYS
WINDOW_END       = now
WINDOW_HUMAN     = human label
DATE_TODAY       = ISO YYYY-MM-DD
EXEC_SLUG        = hyphenated lowercase name
OUTFILE          = ./<EXEC_SLUG>-territory-<DATE_TODAY>.(html|txt)
SCRATCHPAD       = session scratchpad dir
CACHE_DIR        = <SCRATCHPAD>/territory-brief/<EXEC_SLUG>/
GONG_AVAILABLE   = true | false  (set in Phase -1)
```

---

## Phase 1 — Org Discovery from Salesforce (identical to exec-brief Phase 1)

Phases 1a–1d are **identical to exec-brief**. Run the same SOQL queries, strategies, and
cross-checks. Store `SELLER_ROSTER[]` and the full account map.

### Key difference from exec-brief: no account cap

Territory-brief does **not** apply the MAX_FOCUS_ACCOUNTS (50) cap. Every account in the
roster is in scope. AE-level rollups aggregate all accounts — no tier-2 truncation.

### 1e. AE health scoring (replaces exec-brief's focus-account scoring)

Score per AE (not per account):

| Signal | Points |
|---|---|
| Open pipeline ≥ $1M | +40 |
| Account with open escalated case | +30 |
| Account with no Gong call in period (gap) | +20 |
| Renewal in 90 days | +30 |
| Consumption forecast < 85% at any account | +20 |
| Closed lost in period | +15 |
| Matches FOCUS_CONTEXT theme | +15 |

`FOCUS_AES` = all AEs, ranked by score. No cap — all AEs appear in the report.

**Report to user:**
```
<EXEC_NAME>: <R> RDs · <A> AEs · <M> customers + <P> prospects.
Territory scope: <N> total accounts across the full book.
Starting territory intelligence streams…
```

---

## Phase 2 — Intelligence Streams (summary spec; full spec is follow-on)

All streams dispatched in a single message.

### TB-1 · Salesforce Territory Deep Dive
Same as exec-brief SA-4 but scoped to the full roster (no account cap). Produces:
- Pipeline by AE: open amount, stage distribution, renewal count, closed lost in period
- At-risk accounts: escalated cases, renewals ≤90d, no activity in period
- Territory pipeline waterfall: committed vs best-case vs at-risk

### TB-2 · PowerBI Consumption — all accounts
Same `pbi-extract.py` call as exec-brief SA-5. Filter to full roster. Produce:
- AE-level consumption roll-up: accounts at-risk, avg health score, accounts below 85% forecast
- Territory consumption heatmap data (for HTML output)

### TB-3 · Gong Call Coverage (when `GONG_AVAILABLE=true`)
For each AE in the roster:
- Search Gong calls in WINDOW by AE name/email: `mcp__gong__search_calls(query=AE_NAME, ...)`
- Record: accounts touched, last call date, total calls
- Gap report: accounts with 0 Gong calls in the period
- Open commitments: DT-owned `commitments[]` across all calls (ownership-corrected by AE)

Cap: `MAX_AE_GONG_ACCOUNTS` accounts per AE; total transcript retrieval = `GONG_MAX_CALLS` per AE.

### TB-4 · Email + Slack (exec-level only)
Lightweight version of exec-brief SA-2+SA-3. Exec-keyed only — no per-account passes.
Purpose: surface leadership signals, territory-level directives, exec escalations.

---

## Phase 3 — Synthesis (summary spec)

One agent · effort xhigh · reads ONLY merged.json.

### Report sections

| # | Anchor | Content |
|---|---|---|
| 1 | `#territory-summary` | BLUF: territory health in 4–5 sentences with at-risk count, pipeline total, avg health score, top concern |
| 2 | `#ae-health` | AE-level table: name · accounts · open pipeline · renewal count · avg health · Gong call count · last call date · risk badge |
| 3 | `#at-risk` | Accounts flagged by ≥2 risk signals: escalation + consumption below threshold + no call coverage. Grouped by AE |
| 4 | `#call-coverage` | Gong gap report: accounts with no calls in period, by AE. Total: N accounts with zero coverage. Placeholder if Gong not connected |
| 5 | `#open-commitments` | Consolidated DT-owned Gong commitments across territory, sorted by AE, with dueHint where available |
| 6 | `#pipeline` | Pipeline waterfall by RD/AE, renewals calendar, expansion observations |
| 7 | `#consumption` | Territory-wide consumption table and heatmap (HTML) |
| 8 | `#action-items` | Consolidated, numbered. Territory-level: coach AE X on coverage, escalate account Y, focus attention on Z renewal |

---

## Phase 4 — QA Gate (summary spec)

`scripts/qa-check.py` is not yet updated for territory-brief sections. Until it is: run
adversarial QA agent only (no scripted gate). Update qa-check.py in follow-on PR.

---

## Phase 5 — Deliver

Write OUTFILE to current directory. Chat: BLUF + top 3 action items + AE coverage gaps.

---

## Error Handling

Same as exec-brief error table. Additional:

| Failure | Action |
|---|---|
| Gong absent | `GONG_AVAILABLE=false`; call-coverage section renders "Gong not connected — install from se-mcp-servers"; open-commitments section omitted |
| AE with no Salesforce accounts | Listed in Data Notes; excluded from AE-health table |
| PowerBI roster match < 50% | Note in Data Notes; proceed with what matched |

---

## KNOWN LESSONS (inherited from exec-brief)

Apply all 14 exec-brief KNOWN LESSONS. Territory-brief additions:

15. **No per-account agent for Gong coverage.** One search per AE, code-side grouping.
    Never spawn one agent per AE — that pattern burns tokens at scale (50 AEs × one agent each).
16. **AE health table drives the brief.** All other sections reference back to it.
    The table is the primary artifact; synthesis uses it as the spine.

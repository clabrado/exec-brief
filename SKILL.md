---
name: exec-brief
description: >
  Executive intelligence briefing for a Dynatrace Executive Leader.
  Designed to run in the claude-work (Claude Enterprise) environment. Takes the exec's name
  as the primary key, autonomously discovers their org (RDs → AEs → accounts) from Salesforce,
  prioritizes accounts with upcoming customer meetings, open support cases, and recent activity,
  then runs six parallel intelligence streams — M365 calendar + email (claude.ai Enterprise
  connector), Slack (claude.ai Enterprise connector), Salesforce (opportunities + support
  tickets + notes), PowerBI consumption, and LinkedIn + public news — and synthesizes one
  executive brief: BLUF summary, per-meeting prep cards, DT usage/POC status, verified
  struggles, consumption health, pipeline/expansion, public intelligence, and a numbered
  action list. Outputs text (default), branded HTML, or PDF. Every finding is fact-backed
  from a cited source; nothing is fabricated.
argument-hint: '"<exec-name>" [period] [--html|--text|--pdf] [optional context text]'
when_to_use: >
  When a Dynatrace Executive Leader needs a full-footprint briefing ahead of customer meetings,
  a board or leadership cycle, or a QBR sweep: which customers they are meeting, what those
  customers are doing with Dynatrace, where they are struggling, how consumption looks, what
  pipeline exists, and what is happening publicly around DT and those companies. Requires the
  exec's name. Run under the claude-work alias (Claude Enterprise). Triggered by: /exec-brief,
  "brief me for my meetings", "exec briefing for <name>", "prep <name> for the next 2 weeks",
  "leader brief".
---

# /exec-brief — Executive Meeting Intelligence Briefing

One command → one executive-grade brief. The exec's name is the primary key: it resolves
their Salesforce identity, discovers their org hierarchy and account footprint, scopes every
search in Outlook/Teams/SharePoint, Slack, Salesforce, PowerBI, LinkedIn, and public news,
then anchors the report on the customer meetings sitting on their calendar in the chosen window.

Design lineage: `se-brief` (window parsing, M365/Slack subagent patterns, scoring model) and
`dt-rd-review` v4 (org discovery, schema-forced parallel collection, cache-file phase
separation, branded HTML app shell, scripted QA gate). Do not re-derive what those skills
proved — the KNOWN LESSONS section imports their hard-won rules.

---

## PORTABILITY & CONFIG

All tenant/path-specific values live here. Adapting for a different org edits only this block.

```
CONFIG:
  SF_ORG_ALIAS          = dynatrace-sf
  POWERBI_APP_ID        = ccd98e24-9039-4a7f-bc70-b7bea4e85b59   (Dynatrace ONE)
  PBI_EXTRACTOR         = ~/.claude/skills/dt-rd-review/scripts/pbi-extract.py
  PBI_MCP_TOOL          = mcp__powerBI__dynatrace_one_grid
  LOGO_PNG              = ~/dt_deck_assets/logo_white_wordmark_v6.png
  OUTPUT_DIR            = current working directory
  SHARED_REFERENCE      = ~/.claude/skills/dt-customer-review/references/account-intel-shared.md
  HTML_TEMPLATE         = ~/.claude/skills/exec-brief/templates/report-template.html
  QA_SCRIPT             = ~/.claude/skills/exec-brief/scripts/qa-check.py
  MAX_FOCUS_ACCOUNTS    = 50        # hard cap on per-account deep-dive
  MAX_NEWS_COMPANIES    = 12        # cap on SA-6 LinkedIn/news passes
  DT_NEWS_QUERIES       = ["Dynatrace earnings OR acquisition OR partnership OR Gartner",
                           "Dynatrace AI observability announcement OR product launch"]
```

---

## Usage

```
/exec-brief "Nishant Rama"
/exec-brief "Nishant Rama" 2w --html
/exec-brief "Nishant Rama" 3w --html focus on at-risk renewals and prepare for board meeting
/exec-brief "Sarah Chen" last month --text competitive pressure from Datadog in the region
/exec-brief "Dom Miller" 2026-07-01:2026-08-06 --pdf
```

---

## Phase -1 — MCP Pre-flight Check (ALWAYS FIRST)

Before parsing arguments or touching any data source, verify that every required integration
is present and authenticated. Failing fast here prevents wasted collection effort.

Run all probes in parallel. Print a status table, then gate on the result.

### Required integrations

This skill is designed for the **claude-work (Claude Enterprise)** environment. Registered
MCPs in that environment: salesforce, salesforce-auth, powerBI, linkedin, successFactors,
playwrght, and others. The M365 and Slack connectors are **claude.ai Enterprise built-ins**
and will NOT appear in `claude mcp list` output — they are probed directly.

| Integration | How to check | Auth method |
|---|---|---|
| Salesforce | `mcp__salesforce__run_soql_query("SELECT Id FROM User LIMIT 1")` — success = ready | OAuth via `mcp__salesforce-auth__browser_login` |
| PowerBI | `mcp__powerBI__token_status()` | OAuth via `mcp__powerBI__browser_login` |
| M365 connector (Enterprise built-in) | `mcp__claude_ai_Microsoft_365__get_me()` — **not in `claude mcp list`**; probe directly | claude.ai Enterprise-managed; NO OAuth step |
| Slack connector (Enterprise built-in) | `mcp__claude_ai_Slack__slack_search_public_and_private(query="test",limit=1)` — **not in `claude mcp list`**; probe directly | claude.ai Enterprise-managed; NO OAuth step |

### Optional integrations (skill degrades gracefully when absent)

| Integration | Registered in claude-work? | Auth method | Fallback |
|---|---|---|---|
| LinkedIn | ✅ yes — `mcp__linkedin__` | OAuth via `mcp__linkedin__browser_login` | WebSearch + WebFetch on public LinkedIn pages |
| SuccessFactors | ✅ yes — `mcp__successFactors__` | OAuth via `mcp__successFactors__browser_login` | Role/territory SF strategy only |

Note: `m365-copilot` MCP (`mcp__m365-copilot__*`) is **not registered in claude-work** —
do not reference or attempt to use it. The M365 Enterprise connector above is the correct
integration for email and calendar data.

### Pre-flight procedure

**Step 1 — Determine what local MCPs are registered:**

```bash
claude mcp list 2>/dev/null
```

Parse the output for: `salesforce`, `salesforce-auth`, `powerBI`, `linkedin`,
`successFactors`. These are local MCPs and WILL appear in the list when registered.

**The M365 and Slack connectors are claude.ai Enterprise built-ins.** They are NOT local
MCPs and will NOT appear in `claude mcp list`. Probe them directly in step 2.

**Step 2 — Probe and authenticate in parallel:**

For each REQUIRED integration:
- **claude.ai connectors (M365, Slack):** call the probe directly. If it fails with an
  explicit connector error (not an empty result), mark as UNAVAILABLE. Empty results are
  valid — the connector is present, the mailbox/workspace just had no matching items.
- **Local MCPs with token_status:** call `token_status()`. If the result is authenticated
  → READY. If unauthenticated → call `browser_login()` (OAuth), then poll `token_status()`
  every 60s until authenticated or the user confirms. If the MCP is not registered at all
  → MISSING.

For each OPTIONAL integration:
- Same probe + OAuth flow, but a MISSING or unauthenticated optional integration sets a
  `DEGRADED` flag, not a failure. Note the degraded source in Data Notes.
- **LinkedIn specifically:** if the MCP is MISSING (not just unauthenticated), set
  `LINKEDIN_MODE=webfetch` — SA-6 will use `WebSearch` + `WebFetch` on public LinkedIn
  company pages instead of the MCP. If the MCP is present but unauthenticated, attempt
  `browser_login` once; on failure, also fall back to `LINKEDIN_MODE=webfetch`.

**Step 3 — Gate:**

Print the status table:
```
MCP Pre-flight · <DATE_TODAY>
─────────────────────────────────────────────────────
✅ Salesforce        ready
✅ PowerBI           ready (bearer TTL ~52 min)
✅ M365 connector    ready (claude.ai-managed)
✅ Slack connector   ready (claude.ai-managed)
⚠️  LinkedIn         degraded — using WebSearch fallback
⚠️  SuccessFactors   not registered — SF hierarchy strategy only
⚠️  M365 Copilot     not registered — Copilot layer omitted
─────────────────────────────────────────────────────
```

If ANY REQUIRED integration is MISSING (not merely unauthenticated):
```
BLOCKED: <Integration> MCP is not registered in this Claude environment.
The exec needs this MCP installed before /exec-brief can run.
To install: claude mcp add-json --scope user <name> '<config>'
See CLAUDE.md §MCP Notes for the registration pattern.
```
STOP. Do not proceed to Phase 0. List only the missing required MCPs.

If a REQUIRED integration is unauthenticated and OAuth fails (user does not complete the
browser login), STOP with the same message, noting "authentication incomplete."

If all REQUIRED integrations are ready (or DEGRADED on optionals only) → proceed to Phase 0.

---

## Phase 0 — Parse Arguments & Initialize

### Arguments (in order)

1. **`$EXEC_NAME`** (required, quoted if spaces) — primary key for all lookups. If omitted,
   print usage and ask. NEVER assume, default, or reuse a name from prior conversation context.
2. **`$PERIOD`** (optional, default `2w`):

| Form | Example | Meaning |
|---|---|---|
| Shorthand | `1w` `2w` `3w` `4w` `10d` | N weeks/days |
| Words | `2 weeks`, `last month`, `this quarter` | Calendar-aligned |
| ISO range | `2026-07-01:2026-08-01`, `2026-07-01:today` | Explicit start:end |

3. **Output flag** — `--html` | `--text` | `--pdf`. Default `--text`.
4. **`$FOCUS_CONTEXT`** (optional) — ALL remaining freeform text after flags. The exec's
   shaping input. Injected into focus-account scoring, every subagent prompt, and synthesis.

### Derived values

```
PERIOD_DAYS      = normalized integer (1w→7, 2w→14, "last month"→30, ISO delta)
WINDOW_START     = now − PERIOD_DAYS       (signal lookback: email, Slack, SF activity)
WINDOW_END       = now
LOOKAHEAD_END    = now + PERIOD_DAYS       (calendar lookahead: meetings to prep for)
WINDOW_START_UNIX = epoch seconds          (Slack oldest param)
WINDOW_HUMAN     = "Jul 23 – Aug 20, 2026" label
DATE_TODAY       = ISO YYYY-MM-DD
EXEC_SLUG        = hyphenated lowercase name ("nishant-rama")
OUTFILE          = ./<EXEC_SLUG>-brief-<DATE_TODAY>.(html|txt|pdf)
SCRATCHPAD       = session scratchpad dir (derive at runtime — never hardcode from prior session)
CACHE_DIR        = <SCRATCHPAD>/exec-brief/<EXEC_SLUG>/
LINKEDIN_MODE    = mcp | webfetch           (set in Phase -1)
```

**Period is symmetric:** LOOKAHEAD (meetings to prep) = WINDOW (signal history). ISO range
entirely in the past = retrospective mode (lookback = range, lookahead = 0).

**FOCUS_CONTEXT propagation:** injected verbatim as `FOCUS: <text>` into every subagent
prompt; used in Phase 1e account scoring (+20 pts for theme match); used in synthesis for
section emphasis and BLUF framing. It re-weights coverage — it never replaces standard sections.

**Auth warm-up (executed here, once, sequentially):**

- Ensure `<SCRATCHPAD>/dt_logo_b64.txt` exists (needed for --html):
  ```bash
  base64 -i ~/dt_deck_assets/logo_white_wordmark_v6.png | tr -d '\n' > <SCRATCHPAD>/dt_logo_b64.txt
  ```
- PowerBI: re-check bearer TTL; `browser_login` only if already expired since Phase -1.
- Print to user before Phase 1:
  ```
  Exec Brief · <EXEC_NAME> · meetings <now → LOOKAHEAD_END> · signals <WINDOW_START → now>
  Output: <format> · Focus: <FOCUS_CONTEXT | "(none)">
  ```

---

## Phase 1 — Org Discovery from Salesforce (autonomous; sequential; never user-supplied)

### 1a. Resolve the exec's User record

Nickname-normalize first (Dom → Dominic, Nick → keep, Nish → Nishant), then:
```sql
SELECT Id, Name, Title, Email, UserRole.Name FROM User
WHERE Name LIKE '%<EXEC_SEARCH_TERM>%' AND IsActive = true LIMIT 10
```
- Exactly one match → take it regardless of Title (SF titles lie — live-verified).
- Multiple matches → prefer leadership-flavored titles (RVP, VP, Area VP, Sr Director,
  Director, RD); if still ambiguous, present candidates (Name · Title · Role · Email) and ask.
  This is the **only** permitted up-front question.

Store `EXEC_USER_ID`, `EXEC_EMAIL`, `EXEC_ROLE_NAME`.

### 1b. Descend the org hierarchy (RDs → AEs, 2 levels max)

Run both strategies; union the results:

**Strategy 1 — SF ManagerId:**
```sql
SELECT Id, Name, Title, Email FROM User WHERE ManagerId = '<EXEC_USER_ID>' AND IsActive = true ORDER BY Name
```
For each level-1 with Director/Manager/RVP/RSM title, descend one more level. Zero rows is
normal at Dynatrace (live-verified: an RD had no SF direct reports).

**Strategy 2 — HR truth (authoritative when Strategy 1 is thin):**
`mcp__successFactors__get_org_chart` / `get_direct_reports` 2 levels, if available.
Fallback: UserRole territory parse →
```sql
SELECT Id, Name, Title, Email, UserRole.Name FROM User
WHERE UserRole.Name LIKE '%<TERRITORY_TOKEN>%' AND IsActive = true
```
This over-includes; treat as candidate-finder only. Any seller beyond the reporting structure
is excluded by default and listed once for the user ("also found <Name> — excluded; say the
word to add them"). The exec is always in the roster (execs often carry house accounts).

Store `SELLER_ROSTER[]` = all account-owning IDs (exec + all confirmed AEs + RDs with books).

### 1c. Map the account footprint

Count first:
```sql
SELECT Type, COUNT(Id) cnt FROM Account
WHERE OwnerId IN ('<SELLER_ROSTER_IDS>') AND Type IN ('Customer','Prospect') GROUP BY Type
```

Then pull the full map (LIMIT 1000, page if needed):
```sql
SELECT Id, Name, Type, Industry, BillingState, OwnerId, Owner.Name, Owner.ManagerId
FROM Account WHERE OwnerId IN ('<SELLER_ROSTER_IDS>') AND Type IN ('Customer','Prospect')
ORDER BY Owner.Name, Name
```

Each account: `{accountId, name, type, ae, searchName}`. `searchName` = legal suffixes
stripped (LLC/Inc./Corp./Ltd/Holdings), first 2–3 meaningful words. Prospects stay in —
the spec covers POCs for prospects.

### 1d. Completeness cross-check (mandatory)

Independent derivation:
```sql
SELECT Id, Name, Owner.Name, Owner.Id, Owner.ManagerId FROM Account
WHERE (Owner.ManagerId IN ('<RD_IDS>') OR Owner.ManagerId = '<EXEC_USER_ID>'
       OR Owner.Id = '<EXEC_USER_ID>') AND Owner.IsActive = true
       AND Type IN ('Customer','Prospect') LIMIT 1000
```
Diff vs 1c. Missing owners added to roster, their accounts added to the map, reconciliation
noted in Data Notes.

### 1e. Focus-account selection — the scope engine

A wide RVP footprint (300–1000 accounts) cannot all receive per-account narrative. Score
deterministically using 4 cheap pre-signal pulls + calendar call, then cap at MAX_FOCUS_ACCOUNTS.

**Pre-signals (run in parallel):**

1. **Calendar** — `mcp__claude_ai_Microsoft_365__outlook_calendar_search(afterDateTime=now,
   beforeDateTime=LOOKAHEAD_END)`. Match external attendee domains + subject against
   `searchName` list. → `MEETING_ACCOUNTS` (also passed to SA-1).
   If the connector cannot see the exec's mailbox directly, also run
   `outlook_email_search(query="<EXEC_NAME> meeting", …)` for shared invites; flag
   partial in Data Notes.

2. **Open cases:**
   ```sql
   SELECT AccountId, COUNT(Id) c, SUM(CASE WHEN IsEscalated=true THEN 1 ELSE 0 END) esc
   FROM Case WHERE AccountId IN ('<ALL_IDS>') AND IsClosed = false GROUP BY AccountId
   ```
   (Probe `IsEscalated` availability; drop if it errors, retry without it.)

3. **Recent SF activity:**
   ```sql
   SELECT AccountId, COUNT(Id) c FROM Task
   WHERE AccountId IN ('<ALL_IDS>') AND ActivityDate >= LAST_N_DAYS:<PERIOD_DAYS>
   GROUP BY AccountId
   ```

4. **Open pipeline:**
   ```sql
   SELECT AccountId, SUM(Amount) amt, COUNT(Id) c FROM Opportunity
   WHERE AccountId IN ('<ALL_IDS>') AND IsClosed = false GROUP BY AccountId
   ```

**Scoring (code, not model):**

| Signal | Points |
|---|---|
| Upcoming customer meeting in lookahead | +100 (guarantees inclusion) |
| Escalated / P1 open case | +40 |
| Any open case | +15 (cap +30) |
| Open pipeline ≥ $1M | +40 |
| Open pipeline ≥ $250K | +25 |
| SF activity in lookback window | +10 (cap +20) |
| Prospect with open opportunity (POC) | +15 |
| Matches FOCUS_CONTEXT theme (name/industry keyword) | +20 |

`FOCUS_ACCOUNTS` = top-scored, capped at 50. All `MEETING_ACCOUNTS` included unconditionally.
Accounts below the cap appear only in org-level rollup numbers.

**Sanity gate:** empty roster or empty account map after 1d → STOP, report exactly what each
strategy found, ask.

**Report to user:**
```
<EXEC_NAME>: <R> RDs · <A> AEs · <M> customers + <P> prospects.
Focus set: <F> accounts (<K> with upcoming meetings, <E> with escalated cases).
Starting 6 parallel intelligence streams…
```

---

## Phase 2 — Parallel Intelligence Gathering (6 streams, ONE dispatch)

All dispatched in a single message. Wall-clock = slowest stream. Every subagent call is
**schema-forced** (`{schema: …}` — free-text JSON at scale malformed ~16% of outputs in the
dt-rd-review live run; schema-forcing eliminated the class). Every prompt carries:

```
FOCUS: <FOCUS_CONTEXT or "(none)">
NO-HALLUCINATION CONTRACT: every claim must cite a specific tool result (date + source).
If a search returns nothing, emit dataFound=false and empty arrays.
An empty section is correct. An invented one is a defect.
```

---

### SA-1 · Calendar + Meeting Prioritization

Inputs: `MEETING_ACCOUNTS` pre-pull, WINDOW_START, LOOKAHEAD_END, FOCUS_ACCOUNTS.

Tools: `mcp__claude_ai_Microsoft_365__outlook_calendar_search`, `read_resource` on top 3–5 events per category.

- Page calendar across full window. Classify customer-facing vs internal vs personal (drop).
- For each upcoming customer meeting: set `prepNeeded` and `prepReason` hint.
- Surface notable internal meetings (deal reviews, forecast calls, QBRs) as informational.

Schema: CAL_SCHEMA — upcomingMeetings[], pastMeetings[], internalNotable[], dataFound.

---

### SA-2 · Email Intelligence

Inputs: EXEC_NAME, EXEC_EMAIL, FOCUS_ACCOUNTS searchNames (top 25), WINDOW_START.

Tools: `mcp__claude_ai_Microsoft_365__outlook_email_search` (no auth step; returns metadata+URI; `read_resource` for bodies on top hits).

Passes: exec inbox, escalation sweep, per-account (top 25), action item sweep.

Schema: MAIL_SCHEMA — actionItems[], customerThreads[], escalations[], leadershipSignals[], dataFound.

---

### SA-3 · Slack Intelligence

Inputs: EXEC_NAME, FOCUS_ACCOUNTS searchNames (top 25), WINDOW_START_UNIX.

Tools: `mcp__claude_ai_Slack__slack_search_public_and_private` (no auth step).

Passes: exec pass + per-account (bare / risk / competitive). Max 3 bullets per account.

Schema: SLACK_SCHEMA — execMentions[], accountSignals[], dataFound.

---

### SA-4 · Salesforce Deep Dive

Bulk queries over FOCUS_ACCOUNT_IDS. Queries A–H: open opps, closed won/lost, support cases (incl. escalated), active contracts, tasks, POC opps, account feed.

Schema: SF_DEEP_SCHEMA — openPipeline, closedWon, closedLost, cases, renewals, pocOpps, accountActivity, notes.

---

### SA-5 · PowerBI Consumption (HTTP script, not agent)

Orchestrator runs `python3 <PBI_EXTRACTOR> <CACHE_DIR>/pbi-org.json` directly. One ~3.5s HTTP call returns the full ~500-account org grid. Join to book accounts by SFDC 18-char ID. Fields: Health Score, ACV, Cons Rate Latest/6mo/Δ, Forecasted % at Contract End, Contract End Date, Open ATR, Deployment.

---

### SA-6 · LinkedIn + Public News

Inputs: top MAX_NEWS_COMPANIES (meeting accounts first), EXEC_NAME, DT_NEWS_QUERIES, LINKEDIN_MODE.

DT news + per-company: WebSearch + LinkedIn (MCP or WebFetch fallback). Mandatory DT alignment sentence for every company where news is found (cited public statement → specific DT capability play).

Schema: PUBLIC_SCHEMA — dynatraceNews[], companyIntel[], linkedinAvailable, dataFound.

---

### Data merge

Assemble `CACHE_DIR/merged.json` after all streams land. `--resynthesize` reuses cached merged.json. `--refresh <stream>` re-pulls one stream.

---

## Phase 3 — Synthesis

One agent · effort xhigh. Input = file path to merged.json (Read tool only). Intelligence scoring: Critical → High → Medium → Background. Meeting-first ordering. Verified struggles only (source citation required). Fabrication ban. Correct attribution everywhere.

9 output sections: #exec-summary, #calendar, #key-accounts, #dt-usage, #struggles, #consumption, #opportunities, #public-intelligence, #action-items.

---

## Phase 4 — QA Gate

1. `python3 scripts/qa-check.py <merged.json> <outfile>` — validates anchors, attribution stamps, DOM containment, no light-mode flip, base64 logo, junk patterns.
2. One adversarial QA agent checks fabrication, citation traceability, attribution prose, and FOCUS_CONTEXT honoring.
3. HTML: `open <OUTFILE>` — render-verify before reporting done.

---

## Phase 5 — Deliver

1. Write/confirm OUTFILE; `open` it.
2. Chat: file path + BLUF bullets + top 3 action items.
3. Data Notes: degraded streams, missing PowerBI rows, roster reconciliations, LinkedIn mode.

---

## Error Handling

| Failure | Action |
|---|---|
| Required MCP MISSING | STOP in Phase -1. List missing MCPs. Provide `claude mcp add-json` pattern |
| Exec not found in SF | Show what was searched (incl. nickname expansions); ask |
| Multiple exec matches | Present candidates; ask. Only permitted up-front question |
| LinkedIn MCP absent/fails | Set `LINKEDIN_MODE=webfetch`; webfetch fallback |
| PowerBI bearer stale | One re-login + re-run. Offer labeled cached data if <24h |
| Any subagent crashes | `{error:"failed"}` in merged.json; section renders muted unavailable line |
| Any source empty | `(none in window)` — never omit a section header |

---

## KNOWN LESSONS (from se-brief + dt-rd-review live runs)

1. Schema-force every agent — ~16% free-text JSON failure rate eliminated by {schema:…}.
2. Bulk SOQL beats per-account agents — one WHERE AccountId IN (…) pull + code-side grouping.
3. Cache-file phase separation — collection → cache files; synthesis reads ONLY merged.json by file path.
4. Wide footprint = score, cap, tier — deterministic code scoring; 50-account cap; meetings guaranteed.
5. SF titles lie — SuccessFactors HR is authoritative; always run ownership cross-check (1d).
6. PowerBI = one HTTP call — join by SFDC 18-char ID first; single Playwright extraction fallback only.
7. M365 + Slack are claude.ai connectors — NO auth step; call search tools directly.
8. No hallucination is structural — dataFound flags, citations required, adversarial QA, scripted stamps.
9. HTML: template-copy; dark navy only; instant anchor jumps; two-column fixed-sidebar shell; Write tool only.
10. Dispatch all parallel subagents in ONE message.
11. Attribution everywhere — misattributed action items are credibility-killing defects.
12. Render-verify before "done" — DOM/static checks alone never earn "verified."
13. LinkedIn mode is set in Phase -1 and never re-checked by SA-6.

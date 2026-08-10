---
name: exec-brief
description: >
  Executive intelligence briefing for a Dynatrace Executive Leader.
  Designed to run in the claude-work (Claude Enterprise) environment. Takes the exec's name
  as the primary key, autonomously discovers their org (RDs → AEs → accounts) from Salesforce,
  prioritizes accounts with upcoming customer meetings, open support cases, and recent activity,
  then runs up to seven parallel intelligence streams — M365 calendar + email (claude.ai
  Enterprise connector), Slack (claude.ai Enterprise connector), Salesforce (opportunities +
  support tickets + notes), PowerBI consumption, LinkedIn + public news, and optionally Gong
  call intelligence (SA-7: recent call snippets, customer pain points verbatim, open
  commitments, per-meeting last-call cards) — and synthesizes one executive brief: BLUF
  summary, per-meeting prep cards with Gong last-call context, DT usage/POC status, verified
  struggles, Gong call intelligence section, consumption health, pipeline/expansion, public
  intelligence, and a numbered action list. Gong MCP is auto-installed if not present.
  Use --broad to include AE calls for upcoming-meeting accounts. Outputs text (default),
  branded HTML, or PDF. Every finding is fact-backed from a cited source; nothing is fabricated.
argument-hint: '"<exec-name>" [period] [--html|--text|--pdf] [--broad] [optional context text]'
when_to_use: >
  When a Dynatrace Executive Leader needs a full-footprint briefing ahead of customer meetings,
  a board or leadership cycle, or a QBR sweep: which customers they are meeting, what those
  customers are doing with Dynatrace, where they are struggling, how consumption looks, what
  pipeline exists, what is happening publicly around DT and those companies, and what was
  discussed on recent Gong calls with those accounts. Requires the exec's name. Run under the
  claude-work alias (Claude Enterprise). Triggered by: /exec-brief, "brief me for my meetings",
  "exec briefing for <name>", "prep <name> for the next 2 weeks", "leader brief",
  "what are my meetings this week", "prep me for my customer calls".
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
  GONG_MAX_CALLS        = 15         # max transcripts fetched in SA-7
  GONG_BROAD            = false      # overridden by --broad flag
```

---

## Usage

```
/exec-brief "Nishant Rama"
/exec-brief "Nishant Rama" 2w --html
/exec-brief "Nishant Rama" 3w --html focus on at-risk renewals and prepare for board meeting
/exec-brief "Sarah Chen" last month --text competitive pressure from Datadog in the region
/exec-brief "Dom Miller" 2026-07-01:2026-08-06 --pdf
/exec-brief "Nishant Rama" 2w --html --broad
```

---

## Phase -1 — MCP Pre-flight Check (ALWAYS FIRST)

Before parsing arguments or touching any data source, verify that every required integration
is present and authenticated. Failing fast here prevents wasted collection effort.

Run all probes in parallel. Print a status table, then gate on the result.

### Required integrations

This skill is designed for the **claude-work (Claude Enterprise)** environment. Registered
MCPs in that environment: salesforce, salesforce-auth, powerBI, linkedin, successFactors,
playwright, and others. The M365 and Slack connectors are **claude.ai Enterprise built-ins**
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
| Gong | Optional — `mcp__gong__` | OAuth via `mcp__gong__browser_login` | Omit SA-7; note in Data Notes |

Note: `m365-copilot` MCP (`mcp__m365-copilot__*`) is **not registered in claude-work** —
do not reference or attempt to use it. The M365 Enterprise connector above is the correct
integration for email and calendar data.

**Gong is an optional integration.** First check if it's already installed: run `claude mcp list`
and probe `mcp__gong__token_status()` in parallel with other optional checks.

**Case A — Gong MCP not registered (missing from `claude mcp list`):**
Install it automatically — only when it is truly absent:
```
1. git clone https://github.com/clabrado/se-mcp-servers ~/Projects/se-mcp-servers
   (or git -C ~/Projects/se-mcp-servers pull if already cloned)
2. Read ~/Projects/se-mcp-servers/gong-mcp/README.md for the exact registration JSON
3. Register: claude mcp add-json --scope user gong '<json from README>'
4. Call mcp__gong__browser_login to authenticate
5. Verify with mcp__gong__token_status()
```
Tell the user: "Gong MCP was not installed — I've set it up automatically and logged you in."
If the clone or registration fails, set `GONG_AVAILABLE=false`, note the error, and continue.

**Case B — Gong MCP registered but unauthenticated:**
Call `mcp__gong__browser_login()` once. Poll `mcp__gong__token_status()` every 30s up to 2
minutes. If auth completes → READY. If it times out → `GONG_AVAILABLE=false`, note in Data Notes.

**Case C — Gong ready:** set `GONG_AVAILABLE=true`. SA-7 runs in Phase 2.

Brief always continues regardless of Gong outcome — it is never a blocker.

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
⚠️  Gong             not connected — SA-7 call intelligence omitted
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
4. **`--broad`** (optional flag) — expands SA-7 Gong scope. By default SA-7 only fetches calls
   where the exec is a listed participant. With `--broad`, SA-7 also pulls calls for the top 10
   MEETING_ACCOUNTS (accounts with upcoming meetings), regardless of whether the exec was on the
   call. Only applies when `GONG_AVAILABLE=true`. Safe to pass even if Gong is absent.
5. **`$FOCUS_CONTEXT`** (optional) — ALL remaining freeform text after flags. The exec's
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
GONG_AVAILABLE   = true | false             (set in Phase -1)
GONG_BROAD       = true | false             (set by --broad flag; default false)
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
Starting <6|7> parallel intelligence streams…  (7 when GONG_AVAILABLE=true)
```

---

## Phase 2 — Parallel Intelligence Gathering (6–7 streams, ONE dispatch)

All dispatched in a single message — include SA-7 only when `GONG_AVAILABLE=true`.
Wall-clock = slowest stream. Every subagent call is
**schema-forced** (`{schema: …}` — free-text JSON at scale malformed ~16% of outputs in the
dt-rd-review live run; schema-forcing eliminated the class). Every prompt carries:

```
FOCUS: <FOCUS_CONTEXT or "(none)">
NO-HALLUCINATION CONTRACT: every claim must cite a specific tool result (date + source).
If a search returns nothing, emit dataFound=false and empty arrays.
An empty section is correct. An invented one is a defect.
```

---

### SA-1 · Calendar + Meeting Prioritization — `CAL-<EXEC_SLUG>` · Sonnet · high

Inputs: `MEETING_ACCOUNTS` pre-pull, WINDOW_START, LOOKAHEAD_END, FOCUS_ACCOUNTS.

**Tools:** `mcp__claude_ai_Microsoft_365__outlook_calendar_search`, `read_resource` on
the top 3–5 events per category. No `time_zone` param exists — omit it.

- Page `outlook_calendar_search` across the full window (lookback + lookahead). Classify:
  **customer-facing** (external attendee domain or subject matches a searchName, or
  attendee domain matches an `@<account.com>` pattern) vs internal vs personal (drop).
- For each upcoming customer meeting: set `prepNeeded` and a `prepReason` hint (structural
  flags: exec-level attendees, escalation keyword in subject, first meeting with this account,
  renewal within 90 days). Synthesis fills the substantive prep bullets later from merged.json.
- Also surface notable internal meetings (deal reviews, forecast calls, QBRs with leadership)
  as informational.

```json
SA-1 schema (CAL_SCHEMA):
{
  "type": "object",
  "required": ["upcomingMeetings", "pastMeetings", "internalNotable", "dataFound"],
  "properties": {
    "upcomingMeetings": { "type": "array", "items": {
      "type": "object",
      "required": ["date", "title", "account", "attendees", "meetingType", "prepNeeded"],
      "properties": {
        "date": {"type": "string"}, "title": {"type": "string"},
        "account": {"type": ["string","null"]},
        "attendees": {"type": "array", "items": {"type": "string"}},
        "attendeeTitles": {"type": "array", "items": {"type": "string"}},
        "meetingType": {"enum": ["QBR","EBR","demo","renewal","escalation","intro","POC","other"]},
        "prepNeeded": {"type": "boolean"},
        "prepReason": {"type": ["string","null"]}
      }
    }},
    "pastMeetings": {"type": "array", "items": {
      "type": "object",
      "properties": {"date":{"type":"string"}, "title":{"type":"string"},
        "account":{"type":["string","null"]}, "attendees":{"type":"array","items":{"type":"string"}},
        "meetingType":{"enum":["QBR","EBR","demo","renewal","escalation","intro","POC","other"]}}
    }},
    "internalNotable": {"type": "array", "items": {"type": "string"}},
    "dataFound": {"type": "boolean"}
  }
}
```

**Gong meeting-prep injection (orchestrator code — NOT this agent):** After SA-7 data merges,
the orchestrator adds `gong.snippetsByAccount[account]` data to each upcoming meeting's merged
prep card: most recent call date + themes + any open Dynatrace commitments. If the call was
retrieved via `--broad` (exec wasn't on it), the card notes "via AE call". Synthesis reads this
from merged.json — SA-1 does not interact with Gong.

---

### SA-2 · Email Intelligence — `MAIL-<EXEC_SLUG>` · Sonnet · high

Inputs: EXEC_NAME, EXEC_EMAIL, FOCUS_ACCOUNTS searchNames (top 25), WINDOW_START.

**Tools:** `mcp__claude_ai_Microsoft_365__outlook_email_search` (claude.ai-managed connector;
no auth step; no `time_zone` param; returns metadata + URI only → `read_resource` for bodies
on the top 3–5 material hits per pass).

**Passes (parallel):**
- Exec-keyed inbox scan: `query="<EXEC_NAME>", afterDateTime=WINDOW_START, limit=25`
- Escalation sweep: `query="escalation OR at risk OR churn OR urgent OR executive sponsor
  OR critical case"` same window
- Account-keyed (top 25 focus accounts, meeting accounts first): `query="<searchName>"`
  per account, limit 10 each
- Action item sweep: `query="action item OR follow up OR deadline OR please OR can you"`
  same window

Keep: action items involving the exec, customer escalation threads, leadership signals,
renewal/commercial negotiations, POC status updates. Drop: newsletters, bot mail, banter.
Call `read_resource` on the URI of important items before summarizing.

```json
SA-2 schema (MAIL_SCHEMA):
{
  "type": "object",
  "required": ["actionItems", "customerThreads", "escalations", "leadershipSignals", "dataFound"],
  "properties": {
    "actionItems": {"type": "array", "items": {
      "type": "object",
      "required": ["ask", "from", "date"],
      "properties": {"ask":{"type":"string"}, "from":{"type":"string"}, "date":{"type":"string"},
        "account":{"type":["string","null"]}, "evidence":{"type":"string"}}
    }},
    "customerThreads": {"type": "array", "items": {
      "type": "object",
      "required": ["account", "subject", "date", "summary", "sentiment"],
      "properties": {"account":{"type":"string"}, "subject":{"type":"string"},
        "date":{"type":"string"}, "summary":{"type":"string"},
        "sentiment":{"enum":["positive","neutral","risk","critical"]},
        "evidence":{"type":"string"}}
    }},
    "escalations": {"type": "array", "items": {
      "type": "object",
      "required": ["account", "summary", "date", "evidence"],
      "properties": {"account":{"type":"string"}, "summary":{"type":"string"},
        "date":{"type":"string"}, "evidence":{"type":"string"}}
    }},
    "leadershipSignals": {"type": "array", "items": {
      "type": "object",
      "properties": {"from":{"type":"string"}, "summary":{"type":"string"},
        "date":{"type":"string"}, "evidence":{"type":"string"}}
    }},
    "dataFound": {"type": "boolean"}
  }
}
```

---

### SA-3 · Slack Intelligence — `SLACK-<EXEC_SLUG>` · Sonnet · high

Inputs: EXEC_NAME, FOCUS_ACCOUNTS searchNames (top 25), WINDOW_START_UNIX, WINDOW_HUMAN.

**Tools:** `mcp__claude_ai_Slack__slack_search_public_and_private` (claude.ai-managed
connector; no auth step). `slack_read_thread` to expand open escalation hits.

**Passes (parallel):**
- Exec pass: `query="<EXEC_NAME>", time_range=WINDOW_HUMAN`
- Per account (top 25, meeting accounts first):
  - Bare: `query="<searchName>"`
  - Risk: `query="<searchName> escalation OR risk OR churn OR renewal OR outage"`
  - Competitive: `query="<searchName> Datadog OR Splunk OR New Relic OR Grafana OR Elastic"`

Output **talking points only, never transcripts** — max 3 bullets per account. Categories:
struggles/escalations, competitive intel, team/health mentions, AI-angle discussions.
Expand threads only where an open escalation is likely. Omit noise.

```json
SA-3 schema (SLACK_SCHEMA):
{
  "type": "object",
  "required": ["execMentions", "accountSignals", "dataFound"],
  "properties": {
    "execMentions": {"type": "array", "items": {
      "type": "object",
      "properties": {"summary":{"type":"string"}, "date":{"type":"string"},
        "channel":{"type":"string"}, "from":{"type":"string"}}
    }},
    "accountSignals": {"type": "array", "items": {
      "type": "object",
      "required": ["account", "talkingPoints"],
      "properties": {
        "account": {"type": "string"},
        "struggles": {"type": "array", "items": {"type": "string"}},
        "competitive": {"type": "array", "items": {"type": "string"}},
        "talkingPoints": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "evidence": {"type": "array", "items": {
          "type": "object",
          "properties": {"channel":{"type":"string"}, "date":{"type":"string"},
            "fragment":{"type":"string"}}
        }}
      }
    }},
    "dataFound": {"type": "boolean"}
  }
}
```

---

### SA-4 · Salesforce Deep Dive — `SF-DEEP` · Sonnet · high

**Bulk queries, not per-account agents.** One agent, all queries over FOCUS_ACCOUNT_IDS.

**Tools:** `mcp__salesforce__run_soql_query` (org alias: dynatrace-sf)

**Queries (A–G, run in parallel after confirming field availability):**

A) Open opportunities:
```sql
SELECT Id, Name, StageName, Amount, CloseDate, ForecastCategoryName, NextStep,
       AccountId, Account.Name, Owner.Name, Probability
FROM Opportunity WHERE AccountId IN ('<FOCUS_ACCOUNT_IDS>') AND IsClosed = false
ORDER BY Amount DESC NULLS LAST LIMIT 300
```

B) Closed won (lookback):
```sql
SELECT Id, Name, Amount, CloseDate, Type, AccountId, Account.Name, Owner.Name
FROM Opportunity WHERE AccountId IN ('<FOCUS_ACCOUNT_IDS>') AND IsWon = true
AND CloseDate >= LAST_N_DAYS:<PERIOD_DAYS> ORDER BY CloseDate DESC LIMIT 150
```

C) Closed lost (lookback):
```sql
SELECT Id, Name, Amount, CloseDate, AccountId, Account.Name, Owner.Name
FROM Opportunity WHERE AccountId IN ('<FOCUS_ACCOUNT_IDS>') AND IsWon = false
AND IsClosed = true AND CloseDate >= LAST_N_DAYS:<PERIOD_DAYS>
ORDER BY CloseDate DESC LIMIT 150
```

D) **Support cases (the "support tickets also" requirement):**
```sql
SELECT Id, CaseNumber, Subject, Status, Priority, IsEscalated, CreatedDate,
       LastModifiedDate, AccountId, Account.Name, Description
FROM Case
WHERE AccountId IN ('<FOCUS_ACCOUNT_IDS>')
  AND (IsClosed = false OR ClosedDate >= LAST_N_DAYS:<PERIOD_DAYS>)
ORDER BY IsEscalated DESC, LastModifiedDate DESC LIMIT 300
```
Probe `IsEscalated` and `Priority` field availability by running a `SELECT COUNT()` with
and without those predicates. Remove whichever field errors; note the omission.

E) Active contracts (renewal radar):
```sql
SELECT Id, ContractNumber, Status, StartDate, EndDate, ContractTerm,
       AccountId, Account.Name, Account.Owner.Name
FROM Contract WHERE AccountId IN ('<FOCUS_ACCOUNT_IDS>') AND Status = 'Activated'
AND EndDate >= TODAY ORDER BY EndDate ASC LIMIT 200
```

F) Account activity (tasks + events):
```sql
SELECT Id, Subject, ActivityDate, Status, Owner.Name, What.Name, WhoId
FROM Task WHERE ActivityDate >= LAST_N_DAYS:<PERIOD_DAYS>
AND WhatId IN ('<FOCUS_ACCOUNT_IDS>') ORDER BY ActivityDate DESC LIMIT 200
```

G) POC/eval opportunities on Prospect focus accounts:
```sql
SELECT Id, Name, StageName, Amount, CloseDate, AccountId, Account.Name, Owner.Name
FROM Opportunity WHERE AccountId IN ('<PROSPECT_FOCUS_IDS>')
AND IsClosed = false AND (Name LIKE '%POC%' OR Name LIKE '%POV%' OR Name LIKE '%eval%'
OR Name LIKE '%trial%' OR Name LIKE '%proof%' OR StageName LIKE '%eval%')
ORDER BY CloseDate LIMIT 50
```

H) Account notes/feed (run last; skip and note if unsupported):
```sql
SELECT Id, Body, CreatedDate, ParentId, CreatedBy.Name
FROM FeedItem WHERE ParentId IN ('<FOCUS_ACCOUNT_IDS>')
AND CreatedDate >= <WINDOW_START> ORDER BY CreatedDate DESC LIMIT 100
```

**ACV math:** ACV = TotalPrice ÷ (ContractTerm/12). Never report TCV as ACV. Never query
`TotalContractValue__c` / `EndDate__c` / `ContractValue__c` (non-standard, they fail).
Full field-safety rules: SHARED_REFERENCE §1.

```json
SA-4 schema (SF_DEEP_SCHEMA):
{
  "type": "object",
  "required": ["openPipeline", "closedWon", "closedLost", "cases", "renewals",
               "pocOpps", "accountActivity", "notes"],
  "properties": {
    "openPipeline": {
      "type": "object",
      "required": ["totalAmount", "totalCount", "topDeals", "byStage"],
      "properties": {
        "totalAmount": {"type": "number"},
        "totalCount": {"type": "integer"},
        "byStage": {"type": "object", "additionalProperties": {"type": "object",
          "properties": {"count":{"type":"integer"}, "amount":{"type":"number"}}}},
        "topDeals": {"type": "array", "items": {"type": "object",
          "required": ["account", "name", "stage", "amount", "closeDate"],
          "properties": {"account":{"type":"string"}, "name":{"type":"string"},
            "stage":{"type":"string"}, "amount":{"type":["number","null"]},
            "closeDate":{"type":["string","null"]}, "ae":{"type":"string"},
            "probability":{"type":["number","null"]}, "nextStep":{"type":["string","null"]}}}}
      }
    },
    "closedWon": {"type": "object",
      "properties": {"totalCount":{"type":"integer"}, "totalAmount":{"type":"number"},
        "recentDeals":{"type":"array", "items":{"type":"object",
          "properties":{"account":{"type":"string"},"name":{"type":"string"},
            "amount":{"type":["number","null"]},"closeDate":{"type":"string"}}}}}},
    "closedLost": {"type": "object",
      "properties": {"totalCount":{"type":"integer"}, "totalAmount":{"type":"number"},
        "recentDeals":{"type":"array","items":{"type":"object",
          "properties":{"account":{"type":"string"},"name":{"type":"string"},
            "amount":{"type":["number","null"]},"closeDate":{"type":"string"}}}}}},
    "cases": {
      "type": "object",
      "required": ["openCount", "escalated", "byAccount"],
      "properties": {
        "openCount": {"type": "integer"},
        "escalated": {"type": "array", "items": {"type": "object",
          "required": ["account", "caseNumber", "subject"],
          "properties": {"account":{"type":"string"}, "caseNumber":{"type":"string"},
            "priority":{"type":["string","null"]}, "subject":{"type":"string"},
            "ageDays":{"type":["integer","null"]}, "status":{"type":"string"}}}},
        "byAccount": {"type": "object", "additionalProperties": {
          "type": "object",
          "properties": {"open":{"type":"integer"}, "escalated":{"type":"integer"}}
        }}
      }
    },
    "renewals": {
      "type": "object",
      "required": ["expiring90d", "expiring6mo", "expiring12mo"],
      "properties": {
        "expiring90d": {"type": "array", "items": {"type": "object",
          "properties": {"account":{"type":"string"},"contractNum":{"type":"string"},
            "endDate":{"type":"string"},"ae":{"type":"string"},"term":{"type":["integer","null"]}}}},
        "expiring6mo": {"type": "array", "items": {"type": "object",
          "properties": {"account":{"type":"string"},"contractNum":{"type":"string"},
            "endDate":{"type":"string"},"ae":{"type":"string"}}}},
        "expiring12mo": {"type": "array", "items": {"type": "object",
          "properties": {"account":{"type":"string"},"contractNum":{"type":"string"},
            "endDate":{"type":"string"},"ae":{"type":"string"}}}}
      }
    },
    "pocOpps": {"type": "array", "items": {"type": "object",
      "properties": {"account":{"type":"string"},"name":{"type":"string"},
        "stage":{"type":"string"},"amount":{"type":["number","null"]},
        "closeDate":{"type":["string","null"]},"ae":{"type":"string"}}}},
    "accountActivity": {"type": "array", "items": {"type": "object",
      "properties": {"account":{"type":"string"},"subject":{"type":"string"},
        "date":{"type":"string"},"owner":{"type":"string"}}}},
    "notes": {"type": "string"}
  }
}
```

---

### SA-5 · PowerBI Consumption — HTTP script (NOT an agent)

The orchestrator runs this directly in parallel with launching the five subagents:

```bash
python3 <PBI_EXTRACTOR> <CACHE_DIR>/pbi-org.json
```

- One ~3.5s HTTP call returns the full ~500-account org grid via the report's internal
  `/explore/querydata` endpoint with the harvested AAD bearer. Exit 3 = stale bearer →
  one `mcp__powerBI__browser_login` + re-run. If the endpoint returns 401/403/404 after
  re-auth, fall back to ONE Playwright `browser_run_code_unsafe` scripted extraction (never
  an agentic snapshot loop — that pattern burned 51.8M tokens in a dt-rd-review live run).
- Output shape: `{"rows":[…],"columns":[…]}` with composite multi-line account-name strings.
  Normalize per SHARED_REFERENCE §2. **Join to book accounts by SFDC 18-char ID first**
  (`ACCOUNT_ID_18__C` ↔ accountId); name match is fallback only. Filter client-side to the
  exec's footprint after normalization.
- Fields per account: Health Score, Weighted Health, Risk Level, ACV, Cons Rate Latest /
  6mo avg / Δ vs 3mo, Forecasted % at Contract End, Contract End Date, Open ATR, Deployment.
- Org rollups (all accounts in the exec's footprint, including tier-2). Write `pbi-org.json`.
- Validate against PBI_ORG_SCHEMA (reuse dt-rd-review's schema verbatim).
- If `pbi-org.json` is already <24h old and exec matches the cache manifest: skip the HTTP
  call and note "(using cached PowerBI data as of <timestamp>)" in Data Notes.

---

### SA-6 · LinkedIn + Public News — `PUBLIC-INTEL` · Sonnet · medium

Inputs: top `MAX_NEWS_COMPANIES` companies (meeting accounts first), EXEC_NAME,
DT_NEWS_QUERIES, FOCUS_CONTEXT, `LINKEDIN_MODE` flag.

**Dynatrace public posture:**
- `WebSearch` on each `DT_NEWS_QUERIES` query (last 30 days bias)
- If `LINKEDIN_MODE=mcp`: `mcp__linkedin__search_companies("Dynatrace")` and recent posts
- If `LINKEDIN_MODE=webfetch`: `WebFetch("https://www.linkedin.com/company/dynatrace/posts/")`
  for the public company page feed (public posts are visible without auth)

**Per company (up to MAX_NEWS_COMPANIES):**
- `WebSearch("<company> news site:businesswire.com OR site:prnewswire.com OR site:reuters.com
  OR site:bloomberg.com")` + `WebSearch("<company> AI initiative OR cloud migration OR
  layoffs OR acquisition OR CIO OR earnings")`
- If `LINKEDIN_MODE=mcp`: `mcp__linkedin__search_companies("<company>")` + `get_person_posts`
  for recent executive posts
- If `LINKEDIN_MODE=webfetch`: `WebFetch("https://www.linkedin.com/company/<company-slug>/posts/")`
  (public feed only; no auth required for public company pages)
- **DT alignment sentence (mandatory where news is found):** 1–2 sentences connecting a
  CITED public statement to a specific Dynatrace capability (e.g., "CEO announced GenAI
  rollout in Q2 earnings call → AI Observability + LLM cost tracking play"). Citation
  required. No citation → no alignment claim.

All items: `source` field = URL or "LinkedIn: <company>, <date>". Date always present.

```json
SA-6 schema (PUBLIC_SCHEMA):
{
  "type": "object",
  "required": ["dynatraceNews", "companyIntel", "linkedinAvailable", "dataFound"],
  "properties": {
    "dynatraceNews": {"type": "array", "items": {"type": "object",
      "required": ["headline", "date", "source"],
      "properties": {"headline":{"type":"string"}, "date":{"type":"string"},
        "source":{"type":"string"}, "relevance":{"type":"string"}}}},
    "companyIntel": {"type": "array", "items": {"type": "object",
      "required": ["company", "news"],
      "properties": {
        "company": {"type": "string"},
        "news": {"type": "array", "items": {"type": "object",
          "required": ["headline","date","source","summary"],
          "properties": {"headline":{"type":"string"},"date":{"type":"string"},
            "source":{"type":"string"},"summary":{"type":"string"}}}},
        "linkedinSignals": {"type": "array", "items": {"type": "string"}},
        "dtAlignment": {"type": ["string","null"]}
      }
    }},
    "linkedinAvailable": {"type": "boolean"},
    "dataFound": {"type": "boolean"}
  }
}
```

---

### SA-7 · Gong Call Intelligence — `GONG-INTEL` · Sonnet · high

**Dispatch only when `GONG_AVAILABLE=true`.** Runs in parallel with SA-1 through SA-6.

Inputs: `EXEC_NAME`, `EXEC_EMAIL`, `WINDOW_START` (ISO datetime), `WINDOW_END` (ISO datetime),
`MEETING_ACCOUNTS[]` (top 10 by meeting proximity), `FOCUS_ACCOUNTS[]` (top 25 for snippet
matching), `GONG_BROAD`, `FOCUS_CONTEXT`, `GONG_MAX_CALLS` (15).

**Step 1 — Find relevant calls:**

Default (exec's own calls):
```
mcp__gong__search_calls(query=EXEC_NAME, fromDateTime=WINDOW_START, toDateTime=WINDOW_END)
```

If `GONG_BROAD=true`, additionally search for the top 10 MEETING_ACCOUNTS by meeting proximity:
```
for each MEETING_ACCOUNT.searchName (top 10):
  mcp__gong__search_calls(query=searchName, fromDateTime=WINDOW_START, toDateTime=WINDOW_END)
```
Deduplicate by call ID across both passes.

**Step 2 — Score and cap (deterministic, no model):**

Score each call: exec is participant (+50) · account is a MEETING_ACCOUNT (+30) ·
last 7d (+20) · 7–14d (+10) · 15d+ (+0). Cap at `GONG_MAX_CALLS` calls for transcript retrieval.

```
mcp__gong__get_call_details(call_id=...)  # for participants, duration, account
mcp__gong__retrieve_transcripts(call_ids=[...])  # batch, top GONG_MAX_CALLS only
```

**Step 3 — Snippet extraction (NOT full transcripts; schema-forced):**

For each transcript, extract:
- `themes[]` — top 3 discussion topics, max 8 words each
- `painPoints[]` — customer-stated problems: `{quote: "<verbatim ≤25 words>", minuteMarker: "mm:ss"}`
- `commitments[]` — Dynatrace follow-up statements: `{owner: "DT|Customer", text: "<what>", dueHint: "<date if mentioned>"}`
- `keyQuote` — single most impactful customer statement, verbatim ≤25 words
- Citation: `{callId, date, participants[], durationMin, gongUrl}`

NO full transcripts. `painPoints` and `keyQuote` must be verbatim from the transcript. If a
field cannot be extracted, emit an empty array or null. `dataFound=false` if no calls found.

```json
GONG_SCHEMA:
{
  "type": "object",
  "required": ["execCalls", "broadCalls", "snippetsByAccount", "dataFound",
               "callsSearched", "callsTranscribed"],
  "properties": {
    "execCalls": {"type": "array", "items": {
      "type": "object",
      "required": ["callId", "date", "durationMin", "themes", "painPoints", "commitments"],
      "properties": {
        "callId": {"type": "string"}, "date": {"type": "string"},
        "account": {"type": ["string", "null"]}, "durationMin": {"type": "integer"},
        "participants": {"type": "array", "items": {"type": "string"}},
        "themes": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "painPoints": {"type": "array", "items": {
          "type": "object",
          "properties": {"quote": {"type": "string"}, "minuteMarker": {"type": ["string","null"]}}
        }},
        "commitments": {"type": "array", "items": {
          "type": "object",
          "properties": {"owner": {"type": "string"}, "text": {"type": "string"},
                         "dueHint": {"type": ["string","null"]}}
        }},
        "keyQuote": {"type": ["string", "null"]},
        "gongUrl": {"type": ["string", "null"]}
      }
    }},
    "broadCalls": {"type": "array"},
    "snippetsByAccount": {
      "type": "object",
      "description": "Map of account searchName → call snippets for that account",
      "additionalProperties": {"type": "array", "items": {
        "type": "object",
        "properties": {
          "callId": {"type": "string"}, "date": {"type": "string"},
          "themes": {"type": "array", "items": {"type": "string"}},
          "keyPainPoint": {"type": ["string", "null"]},
          "openCommitment": {"type": ["string", "null"]},
          "viaAeCall": {"type": "boolean"}
        }
      }}
    },
    "dataFound": {"type": "boolean"},
    "callsSearched": {"type": "integer"},
    "callsTranscribed": {"type": "integer"}
  }
}
```

---

### Data merge (orchestrator code — deterministic, never a model)

After all six streams land, assemble `CACHE_DIR/merged.json`:

```json
{
  "exec": "<name>", "execUserId": "…", "periodDays": 14,
  "windowHuman": "…", "focusContext": "…", "generatedAt": "…",
  "org": {
    "rds": [], "aes": [], "totalCustomers": 0, "totalProspects": 0,
    "focusCount": 0, "tier2Rollup": {"totalAccounts": 0, "totalACV": 0}
  },
  "calendar": "<SA-1 result>",
  "email": "<SA-2 result>",
  "slack": "<SA-3 result>",
  "sf": "<SA-4 result>",
  "pbi": "<SA-5 normalized+filtered>",
  "public": "<SA-6 result>",
  "gong": "<SA-7 result or {error:'skipped', gongAvailable:false}>",
  "accounts": [
    {
      "account": "…", "accountId": "…", "ae": "…", "rd": "…",
      "type": "Customer|Prospect", "score": 120, "hasMeeting": true,
      "meetingDates": ["2026-08-10"],
      "sf": { "opps": [], "cases": [], "renewals": [], "activity": [] },
      "pbi": { "healthScore": null, "consRate": null, "…": null },
      "emailSignals": [], "slackSignals": [], "gongSnippets": [],
      "publicIntel": null,
      "dataFound": { "sf": true, "pbi": false, "email": true, "slack": false, "public": false }
    }
  ]
}
```

Failed streams → `{error:"failed"}` on that key. Write `manifest.json` beside it.

`--resynthesize` reuses merged.json when manifest is <24h old and exec matches.
`--refresh <stream>` re-pulls one stream (comma list), rebuilds merged.json, re-synthesizes.

---

## Phase 3 — Synthesis

One agent · `SYNTH-<EXEC_SLUG>` · effort xhigh.
**Input = file path to merged.json** (Read tool). No data-tool access. merged.json is
the entire world for this agent. Never inline the JSON payload in the prompt.

### Intelligence scoring (ranks every item in the brief)

| Signal | Weight |
|---|---|
| Upcoming meeting ≤ 7 days with unresolved escalation OR renewal on table | Critical |
| Escalated support case at a meeting account | Critical |
| Renewal ≤ 90 days AND (health < 60 OR forecast < 85%) | Critical |
| Upcoming meeting with exec-level attendees or POC decision | High |
| Consumption forecast-at-end < 85%, no meeting scheduled | High |
| Public news materially changing account posture (M&A, layoffs, AI initiative) | High |
| Open pipeline ≥ $1M, close ≤ 45 days | High |
| Competitive signal (Slack/email) at a focus account | Medium |
| Expansion signal (cons > 100%, open ATR, POC momentum) | Medium |
| FOCUS_CONTEXT match → bump up one tier | +1 tier |
| Informational / resolved / tier-2 rollup only | Background |

### Synthesis rules

- **Meeting-first:** calendar drives the narrative. Each upcoming customer meeting gets a
  prep block in `#calendar`. Account section cards order by (meeting date first, then score).
- **Verified struggles only:** `#struggles` admits ONLY items with a citable source (Case
  number / Slack channel+date / email subject+date). Cross-source items get `◆ corroborated`
  flag and outrank single-source. Single source is valid — labeled with its source.
- **Fabrication ban:** every number traces to merged.json. Absent field → `—` / `No data`.
  `dataFound=false` on any stream → muted "no signals found" line for that block, never
  invented content. One fabricated figure discredits the whole brief.
- **BLUF discipline:** exec summary = 4–5 complete, opinionated sentences naming an account,
  a number, and an action. No headings, no hedging, no "several accounts show…" vagueness.
- All focus accounts with meetings MUST appear. Tier-2 accounts appear only in rollup
  numbers. Never truncate a meeting account for context length.
- Deduplicate across sources: the same escalation in email + Slack + Case = ONE finding with
  three citations.
- **Correct attribution everywhere:** action items name the owning AE when delegating.
  Never say "AE-X should call <account>" when AE-Y owns it.

### Report sections (all output formats; anchor IDs are the HTML contract)

| # | Anchor | Content |
|---|---|---|
| 1 | `#exec-summary` | BLUF 4–5 bullets. HTML: 6-tile metric row (meetings ahead · escalated cases · renewals ≤90d · open pipeline · focus-set ACV · avg health) |
| 2 | `#calendar` | Upcoming customer meetings chronological: date · account · type badge · attendees+titles · **prep block** (2–4 bullets: usage state, open struggle, consumption, the ask; Gong last-call card when available). Past-window meetings as compact table |
| 3 | `#key-accounts` | Top accounts needing attention, ranked by score: card each with why it's here, owning AE + RD, headline numbers |
| 4 | `#dt-usage` | Per focus account: deployment type, health, what they run; prospects: POC/eval status |
| 5 | `#struggles` | Verified signals table: account · struggle · source(s) · date · status · `◆ corroborated`. Gong `painPoints[]` entries admitted with citation `[Gong call <date> — <participant>]`; cross-source items `◆ corroborated` |
| 6 | `#gong-intelligence` | Gong call summaries grouped by account (meeting accounts first). Per call: date · participants · themes · verbatim pain point quote · open commitments. Header metric: N calls reviewed · N accounts covered · N open commitments surfaced. Renders muted "Gong not connected" placeholder when `GONG_AVAILABLE=false` |
| 7 | `#consumption` | PowerBI table for focus set: ACV · cons rate latest/6mo/Δ · forecast-at-end · contract end · risk badge. Tier-2 org rollup line. "No PowerBI data" where absent |
| 8 | `#opportunities` | Open pipeline by RD, top 10 deals, renewals calendar (90d/6mo/12mo), expansion observations |
| 9 | `#public-intelligence` | DT news block, then per-company: news + LinkedIn signals + **DT alignment** sentence, every item dated + sourced |
| 10 | `#action-items` | Consolidated, numbered, Critical→Low. Each: account · action · why · horizon (this week / before <date> meeting / this month) · owner (exec vs delegate-to-RD/AE, correctly attributed). Gong `commitments[]` with `owner=DT` fed in. Min 5, target 8–12 |

Every section header always renders. Empty data → `(none in window)`.

---

## Output Formats

### `--text` (default)
Markdown-structured, sections in the order above, written to `<OUTFILE>.txt`. Tables as
aligned ASCII. Echo exec summary + action items into chat.

### `--pdf`
Render text-mode content through the standard MD→PDF chain. ASCII diagrams only. Sanitize
customer names per customer-data handling rules if the brief will leave the laptop.

### `--html` — full design spec

**Template-first (mandatory):** the design system lives at `HTML_TEMPLATE`. Synthesis COPIES
the template and fills `<!-- {{SLOT:…}} -->` markers. Never author a stylesheet from scratch.
If the template is missing on first run: generate it from this spec, save to the templates
dir, note it in the run output. CSS/JS in the template must remain byte-identical between
runs (the QA script checks this).

**CSS tokens (from dt-rd-review v4, verbatim):**
```css
:root {
  --bg: #00092F; --bg-card: #0A1A4A; --bg-card2: #0D2060;
  --bg-nav: rgba(0,9,47,0.96);
  --border: rgba(24,102,254,0.18); --border-subtle: rgba(255,255,255,0.07);
  --blue: #1866FE; --purple: #7F1AFE; --green: #01D393;
  --red: #FF3B5C; --orange: #FF8C00; --yellow: #FFD040;
  --text: #E8EEFF; --text-muted: #6B80A8; --text-dim: #8899BB;
  --mono: 'Courier New', ui-monospace, monospace; --sans: Arial, sans-serif;
  --nav-h: 52px; --sidebar-w: 250px;
}
```

**No light-mode CSS flip:** NEVER emit `@media (prefers-color-scheme: light)` that swaps to
a white background. The dark navy canvas `#00092F` is the only permitted base. A JS
`data-theme` toggle is fine; a media-query auto-flip to white is a brand violation and QA-fails.

**Two-column app shell (v4 — v3 floating rail was duct-tape):**
- **Sticky top nav** `position:fixed; height:var(--nav-h)` — left: DT logo (base64 white
  wordmark at ~26px, NO background tile, never a "DT" text logo); center: "<EXEC_NAME> ·
  Executive Brief · <WINDOW_HUMAN>"; right: theme toggle.
- **Persistent left sidebar** `position:fixed; width:var(--sidebar-w)`, full height below
  the header, own `overflow-y:auto`. Two grouped lists:
  - **BRIEF** — the 9 section links with count pills (`Calendar 7` · `Struggles 4` · `Actions 9`)
  - **MEETING ACCOUNTS** — one link per upcoming-meeting account → its `#acct-<slug>` card,
    ordered by meeting date, with a date chip on each link
  Content wrapper `margin-left:var(--sidebar-w)` — content never underlaps the sidebar.
- **Instant anchor jumps, NOT smooth scroll:** `html{scroll-behavior:auto}` and
  `scroll-margin-top:calc(var(--nav-h)+12px)` on EVERY anchor target. Smooth scroll stalls
  on tall reports (these run ~50–90K px) and looks broken.
- **Responsive:** under 1000px the sidebar becomes a hamburger-toggled drawer;
  `margin-left:0`; no horizontal body scroll at any width. Optional lightweight
  IntersectionObserver scrollspy on the sidebar links.

**Components:**
- **Exec-summary hero:** BLUF bullets in a `--green`-left-bordered card + a 6-tile metric
  grid (`--bg-card` bg, value `--green` 2rem bold, label `--muted` uppercase 11px).
- **Meeting prep cards** (`#calendar`): date rail on left (blue), account + meeting-type
  badge, prep bullets; escalation-flavored meetings get a `--red` left border.
- **Section cards:** `background:var(--bg-card); border-radius:8px;
  border:1px solid rgba(24,102,254,.18)`. Chevron toggle (default expanded).
  Section `h2` in `--blue` uppercase letter-spaced.
- **Risk badges:** At-Risk `--red`, High `--orange` (black text), Medium `#FFC107` (black),
  Low `--green` (black), Unknown `#666`. Derive badge from health + consumption thresholds
  when PowerBI `riskLevel` is null: health<50 OR forecast<70 → At-Risk; 50–70 → Medium/High.
  No PowerBI row at all → gray Unknown, never a guess.
- **Struggles table:** source chips per row (`CASE 01294337` / `#slack-channel` / `✉ subject`);
  `◆ corroborated` in `--purple` font-weight bold.
- **Action items:** numbered `--blue` numerals, priority badge, horizon chip, owner chip.
- **Footer:** "Dynatrace Confidential · Generated <date> · <streams> sources · Focus: <context|none>"
  in `#666` 0.75rem.

**Machine-checkable stamps (QA depends on them — missing = QA FAIL):**
- Every account card: `data-account="<name>" data-ae="<ae>" data-rd="<rd>"`
- Every meeting prep card: `data-account="<name>" data-date="<date>"`
- Every action item: `data-account="<name>" data-owner="<owner>"`
- Once in the page: `<script type="application/json" id="report-data">…merged.json…</script>`

**File write:** Write tool ONLY — never a bash heredoc (`$[digit]` expansion silently
corrupts dollar amounts). `<!DOCTYPE html>` … `</html>`. No external CDN dependencies
(all CSS/JS inline). Return `WRITTEN:<path>`.

---

## Phase 4 — QA Gate

### Step 1 — Scripted gate (HTML only; runs in seconds)

```bash
python3 <QA_SCRIPT> <CACHE_DIR>/merged.json <OUTFILE>
```

Verifies: all required anchor IDs present (#gong-intelligence included when `gong.dataFound=true` in merged.json, rendered as muted placeholder when `GONG_AVAILABLE=false`); every upcoming-meeting account has a prep card AND an
account card; account→AE/RD attribution on `data-account`/`data-ae`/`data-rd` stamps matches
merged.json; metric-tile numbers match merged.json rollups; no light-mode CSS flip; base64
logo present; `#report-data` block present; DOM containment (every section inside the content
wrapper, sidebar a direct child of body — tag-count balance alone missed orphan closers in a
dt-rd-review live run); junk patterns (`$NaN`, `undefined`, `[object Object]`, `$$`, `%%`).
Fix every FAIL and re-run until exit 0.

### Step 2 — One adversarial QA agent (all formats)

Label: `Adversarial-QA` · effort: high. "You are a hostile reviewer. Assume the brief is
wrong until proven right." Give it OUTFILE + merged.json path.

Checks ONLY judgment (the script owns arithmetic/structural):
1. No fabricated content on `dataFound=false` streams or accounts.
2. Every `#struggles` row has a real citation existing in merged.json.
3. Every exec-summary claim and every `dtAlignment` sentence traces to a source in merged.json.
4. Action-item owner attribution correct in prose (not just stamps).
5. FOCUS_CONTEXT actually honored in emphasis and framing.

### Render check (HTML)

`open <OUTFILE>` — visually confirm the shell and sidebar render before reporting done.
DOM/static checks alone never earn "verified."

---

## Phase 5 — Deliver

1. Write/confirm OUTFILE in the current directory; `open` it (HTML/PDF).
2. Chat: file path + the BLUF bullets + top 3 action items verbatim.
3. Data Notes: degraded streams, accounts missing PowerBI rows, roster reconciliations,
   LinkedIn mode (mcp vs webfetch), partial-calendar caveat if applicable.

---

## Error Handling

| Failure | Action |
|---|---|
| Required MCP MISSING from environment | STOP in Phase -1. List which MCPs are missing. Tell the exec which MCP they need installed. Provide the `claude mcp add-json` registration pattern |
| Required MCP unauthenticated, OAuth incomplete | STOP in Phase -1 with "authentication incomplete" |
| LinkedIn MCP absent | Set `LINKEDIN_MODE=webfetch`; SA-6 uses WebSearch + WebFetch on public pages; `linkedinAvailable:false` |
| LinkedIn MCP present but auth fails | Same webfetch fallback after one `browser_login` attempt |
| Gong MCP absent | Auto-install from `clabrado/se-mcp-servers` (clone + register + `browser_login`); if install fails, set `GONG_AVAILABLE=false`, skip SA-7, render muted placeholder |
| Gong MCP unauthenticated | Call `browser_login` once, poll 30s×4; on timeout set `GONG_AVAILABLE=false`, skip SA-7, note in Data Notes |
| Exec not found in SF | Show what was searched (incl. nickname expansions); ask for full name or email |
| Multiple exec matches in SF | Present candidates (Name · Title · Role · Email); ask. Only permitted up-front question |
| Roster empty after both strategies | STOP; report Strategy-1 and Strategy-2 results verbatim; ask |
| SuccessFactors unavailable | Role/territory fallback only; mark roster "inferred" in Data Notes |
| Calendar cannot see exec mailbox | Shared/invited-event fallback; flag as partial in Data Notes |
| Case field `IsEscalated`/`Priority` errors | Retry without the offending field; note omission |
| FeedItem subquery unsupported | Skip; note it |
| PowerBI bearer stale mid-run | One re-login + re-run extractor. If still failing: `pbi:{error}` — render "PowerBI unavailable this run." NEVER present stale numbers as current. If cached pbi-org.json <24h exists, offer it explicitly labeled "as of <timestamp>" |
| Any subagent crashes | `{error:"failed"}` in merged.json; section renders muted unavailable line; run continues |
| Slack rate limit | 2s wait, one retry; note and continue |
| Any source empty | `(none in window)` — never omit a section header |

---

## KNOWN LESSONS (from se-brief + dt-rd-review live runs — do not bypass)

1. **Schema-force every agent.** Free-text JSON at scale malformed ~16% of outputs (19/121
   losses in the dt-rd-review live run). `{schema:…}` on every call; merge in code, not by model.
2. **Bulk SOQL beats per-account agents.** One `WHERE AccountId IN (…)` pull + code-side
   grouping replaced per-account SF agents and removed the whole parse-failure class.
3. **Cache-file phase separation.** Collection → cache files; synthesis reads ONLY merged.json
   by FILE PATH. `--resynthesize`/`--refresh` iterate on layout without repulling. Never clobber
   good cache; never spelunk journals.
4. **Wide footprint = score, cap, tier.** Score deterministically in code; cap at 50 focus
   accounts; meetings guarantee inclusion; tier-2 appears only in rollup numbers.
5. **The reporting structure defines the roster.** SF titles lie; HR (SuccessFactors) is
   authoritative. Role/territory queries over-include; always run ownership cross-check (1d).
6. **PowerBI = one HTTP call.** `pbi-extract.py`/`dynatrace_one_grid`. Join grid↔book by SFDC
   18-char ID first (name-only once double-attached a $1.4M account). Single Playwright
   `browser_run_code_unsafe` extraction is the only permitted fallback (the agentic-snapshot
   loop burned 51.8M tokens once).
7. **M365 + Slack are claude.ai connectors — NO auth step.** Call the search tools directly.
   `outlook_email_search` has no `time_zone` param; returns metadata+URI only (read_resource
   for bodies). Slack `oldest` is epoch seconds. Do NOT confuse with `mcp__m365-copilot__*`
   (a separate Copilot AI assistant MCP — a different integration entirely).
8. **No hallucination is structural.** dataFound flags, citations required for #struggles,
   `—`/`No data` for absent fields, adversarial QA hunting fabrication on dataFound=false,
   scripted stamp checks. Empty stays empty.
9. **HTML:** template-copy not improvised design; dark navy only (no prefers-color-scheme
   light flip); instant anchor jumps + scroll-margin-top (smooth scroll stalls on tall reports);
   two-column fixed-sidebar shell (not a floating rail); Write tool only (never heredoc);
   DOM-containment QA (tag counts alone missed orphan closers).
10. **Dispatch all parallel subagents in ONE message.** Wall-clock = slowest. Concurrency
    ceiling is min(16, cores−2) — waves, not 100-wide. Include SA-7 in the same dispatch
    when `GONG_AVAILABLE=true`; do NOT dispatch it separately after the others complete.
11. **Attribution everywhere.** Misattributed "AE-X should call <AE-Y's account>" is a
    credibility-killing defect, caught by both the script (stamps) and adversarial agent (prose).
12. **Render-verify before "done."** Open the HTML; DOM/static checks alone never earn "verified."
13. **LinkedIn mode is set in Phase -1 and never re-checked.** SA-6 reads `LINKEDIN_MODE` as
    a parameter, not an environment probe. If it is `webfetch`, it uses WebSearch + WebFetch
    for all LinkedIn-equivalent content without attempting MCP tools.
14. **Gong = snippets, not transcripts.** SA-7 caps at `GONG_MAX_CALLS` (15) and schema-forces
    extraction to `themes[]`, `painPoints[]` (verbatim ≤25 words), `commitments[]`, `keyQuote`.
    Full transcripts are never stored or surfaced in the brief. `--broad` expands search scope
    to meeting-account AE calls but the transcript cap still applies.

# /exec-brief — Executive Intelligence Briefing

A Claude Code skill for **Dynatrace Executive Leaders** (RVP, VP, Area VP level). One command pulls calendar, email, Slack, Salesforce, PowerBI, LinkedIn, and public news into one cited, fact-backed brief — meeting prep cards, verified struggles, consumption health, pipeline snapshot, and ranked action items.

> **Environment:** Requires `claude-work` (Claude Enterprise). Does not run in the personal `claude-eco` environment — M365 and Slack require the claude.ai Enterprise connectors.

---

## Usage

```bash
/exec-brief "Nishant Rama"
/exec-brief "Nishant Rama" 2w --html
/exec-brief "Nishant Rama" 3w --html focus on at-risk renewals
/exec-brief "Dom Miller" last month --pdf
/exec-brief "Sarah Chen" 2026-07-01:2026-08-06 --text competitive pressure from Datadog
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `"Exec Name"` | Yes | Primary key for all lookups. Always quote if name has spaces. Never omit or reuse from prior context. |
| Period | No | `2w` (default), `1w`, `3w`, `4w`, `10d`, `last month`, `this quarter`, or ISO range `2026-07-01:today` |
| `--html` | No | DT-branded interactive HTML report with sidebar nav, meeting prep cards, risk badges |
| `--text` | No | Markdown output (default) |
| `--pdf` | No | PDF output, sanitized for distribution |
| Focus context | No | Any freeform text after the flags — injected into every stream and synthesis to re-weight coverage |

### Iteration flags

```bash
/exec-brief "Nishant Rama" 2w --html --resynthesize      # Re-run synthesis from cached data (no repull)
/exec-brief "Nishant Rama" 2w --html --refresh slack      # Refresh one stream, rebuild merged.json
```

---

## MCP Prerequisites

The skill runs a pre-flight check (Phase -1) before touching any data. It will print a status table and block with instructions if a required integration is missing.

### Required — skill blocks if any of these are absent or fail OAuth

| Integration | MCP namespace | Auth |
|---|---|---|
| Salesforce | `mcp__salesforce__` + `mcp__salesforce-auth__` | OAuth via `mcp__salesforce-auth__browser_login` |
| PowerBI | `mcp__powerBI__` | OAuth via `mcp__powerBI__browser_login` |
| M365 (email + calendar) | claude.ai Enterprise built-in — **not in `claude mcp list`** | claude.ai-managed, no OAuth step |
| Slack | claude.ai Enterprise built-in — **not in `claude mcp list`** | claude.ai-managed, no OAuth step |

> **Note:** The `mcp__m365-copilot__*` MCP is a separate Copilot AI assistant integration and is **not used by this skill**. The M365 Enterprise connector above is what provides email and calendar data.

### Optional — skill degrades gracefully

| Integration | MCP namespace | Fallback if absent |
|---|---|---|
| LinkedIn | `mcp__linkedin__` | WebSearch + WebFetch on public LinkedIn pages |
| SuccessFactors (HR) | `mcp__successFactors__` | SF hierarchy + role/territory strategy only |

### Registering a missing MCP

```bash
claude mcp add-json --scope user <name> '<json config>'
```

See `CLAUDE.md §MCP Notes` for registration patterns. Run `claude mcp list` to see what's currently registered in your environment.

---

## What it produces

| Section | Content |
|---|---|
| **Executive Summary** | 4–5 BLUF bullets naming an account, a number, and an action. HTML adds a 6-tile metric row (meetings · escalated cases · renewals ≤90d · pipeline · focus ACV · avg health). |
| **Calendar / Meeting Prep** | Upcoming customer meetings in chronological order, each with a prep card: attendees + titles, meeting type, and 2–4 prep bullets (usage state, open struggle, consumption posture, the ask). |
| **Key Accounts** | Top accounts ranked by focus score — why each is flagged, owning AE + RD, headline numbers. |
| **DT Usage** | Deployment type, health, product footprint per focus account; POC/eval status for prospects. |
| **Struggles** | Source-cited signals only. Every row requires a citation (Case # / Slack channel+date / email subject+date). Cross-source items flagged ◆ corroborated. |
| **Consumption** | PowerBI table: ACV · cons rate (latest/6mo/Δ) · forecasted % at contract end · end date · risk badge. "No PowerBI data" where absent — never a guess. |
| **Opportunities** | Open pipeline by RD, top 10 deals by amount, renewals calendar (90d/6mo/12mo), expansion signals. |
| **Public Intelligence** | DT news block, then per-company: dated + sourced headlines, LinkedIn signals, and a DT alignment sentence (cited public statement → specific capability play). |
| **Action Items** | Consolidated and ranked Critical→Low. Each item: account · action · urgency · horizon · owner (exec vs delegate to RD/AE). |

---

## How it works

```
Phase -1  MCP Pre-flight     All integrations probed + OAuth'd in parallel. Blocks on missing required.
Phase 0   Parse & Init       Resolves exec name, window, output format, focus context.
Phase 1   Org Discovery      Salesforce → exec User ID → org hierarchy (RDs→AEs) → account footprint →
                             focus-account scoring (capped at 50; meeting accounts always guaranteed).
Phase 2   Parallel Streams   6 intelligence streams dispatched simultaneously:
                               SA-1  M365 Calendar — meeting classification + prep flags
                               SA-2  M365 Outlook  — inbox scan, escalations, account threads
                               SA-3  Slack         — exec pass + per-account risk/competitive passes
                               SA-4  Salesforce    — bulk SOQL: opps, cases, contracts, activity, POCs
                               SA-5  PowerBI       — one HTTP call via pbi-extract.py (~3.5s, all accounts)
                               SA-6  LinkedIn/News — DT news + per-company public intel + alignment
Phase 3   Synthesis          xhigh-effort agent reads merged.json by file path. No live data access.
Phase 4   QA Gate            scripts/qa-check.py (structural) + adversarial agent (fabrication check).
Phase 5   Deliver            Output file + BLUF + top 3 actions to chat.
```

### Key design guarantees

- **No hallucination:** every finding requires a cited source. `dataFound=false` on any stream renders only a muted "no signals found" line — never invented content.
- **Schema-forced subagents:** eliminates the ~16% free-text JSON failure rate observed at scale.
- **Meeting-first:** calendar drives the narrative; accounts with upcoming meetings are guaranteed in the focus set regardless of the 50-account cap.
- **Bulk SOQL:** one `WHERE AccountId IN (…)` query covers all focus accounts — no per-account agent failure class.
- **PowerBI = one HTTP call:** `pbi-extract.py` returns all ~500 org accounts in ~3.5s.
- **Cache-resume:** `--resynthesize` reruns synthesis without repulling any source. Good data is never clobbered.

---

## Focus-Account Scoring

With 300–1000 accounts in an RVP footprint, the skill scores deterministically in code and caps at 50 focus accounts before any per-account narrative runs.

| Signal | Points |
|---|---|
| Upcoming customer meeting in lookahead window | +100 (always included) |
| Escalated / P1 open support case | +40 |
| Open pipeline ≥ $1M | +40 |
| Open pipeline ≥ $250K | +25 |
| Matches FOCUS_CONTEXT keyword | +20 |
| Prospect with open POC opportunity | +15 |
| Any open support case (cap +30 total) | +15 |
| SF activity in lookback window (cap +20 total) | +10 |

---

## Files

```
SKILL.md                   Full skill specification (phases, schemas, error handling)
scripts/qa-check.py        Scripted QA gate — validates HTML report structure and attribution
exec-brief-overview.pdf    One-page overview for sharing with stakeholders
```

---

## Output location

All output files land in the **current working directory** when the skill is invoked. File naming: `<exec-slug>-brief-<date>.(html|txt|pdf)`.

---

*Requires claude-work (Claude Enterprise). Designed and maintained by the Dynatrace NORAM SE team.*

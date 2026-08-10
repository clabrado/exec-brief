# /exec-brief + /territory-brief — Executive Intelligence Briefing

Claude Code skills for **Dynatrace Executive Leaders** (RVP, VP, Area VP, RD level). One command pulls calendar, email, Slack, Salesforce, PowerBI, LinkedIn, public news, and **Gong call recordings** into one cited, fact-backed brief — meeting prep cards with last-call context, verified struggles, consumption health, pipeline snapshot, and ranked action items.

> **Environment:** Requires `claude-work` (Claude Enterprise). M365 and Slack require the claude.ai Enterprise connectors. Gong is auto-installed if not present — no manual setup needed.

---

## Skills

| Skill | Command | Purpose |
|---|---|---|
| exec-brief | `/exec-brief` | Meeting-prep focused brief for an exec: upcoming customer meetings, per-account deep dives, Gong last-call cards |
| territory-brief | `/territory-brief` | Territory health view for an RD/RVP: AE-level pipeline, Gong call coverage gaps, at-risk accounts |

---

## Usage

```bash
# exec-brief
/exec-brief "Nishant Rama"
/exec-brief "Nishant Rama" 2w --html
/exec-brief "Nishant Rama" 3w --html focus on at-risk renewals
/exec-brief "Nishant Rama" 2w --html --broad          # also pull AE Gong calls for meeting accounts
/exec-brief "Dom Miller" last month --pdf
/exec-brief "Sarah Chen" 2026-07-01:2026-08-06 --text competitive pressure from Datadog

# territory-brief
/territory-brief "Nishant Rama"
/territory-brief "Nishant Rama" 4w --html
/territory-brief "Dom Miller" last quarter --html
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `"Exec Name"` | Yes | Primary key for all lookups. Always quote if name has spaces. Never omit or reuse from prior context. |
| Period | No | `2w` (default), `1w`, `3w`, `4w`, `10d`, `last month`, `this quarter`, or ISO range `2026-07-01:today` |
| `--html` | No | DT-branded interactive HTML report with sidebar nav, meeting prep cards, risk badges |
| `--text` | No | Markdown output (default) |
| `--pdf` | No | PDF output, sanitized for distribution |
| `--broad` | No | Expand Gong scope to include AE calls for upcoming-meeting accounts (not just exec's own calls) |
| Focus context | No | Any freeform text after the flags — injected into every stream and synthesis to re-weight coverage |

### Iteration flags

```bash
/exec-brief "Nishant Rama" 2w --html --resynthesize      # Re-run synthesis from cached data (no repull)
/exec-brief "Nishant Rama" 2w --html --refresh slack      # Refresh one stream, rebuild merged.json
```

---

## MCP Prerequisites

The skill runs a pre-flight check (Phase -1) before touching any data. Required MCPs that fail will block with setup instructions. Optional MCPs — including Gong — are **auto-installed** if missing.

### Required — skill blocks if any of these are absent or fail OAuth

| Integration | MCP namespace | Auth |
|---|---|---|
| Salesforce | `mcp__salesforce__` + `mcp__salesforce-auth__` | OAuth via `mcp__salesforce-auth__browser_login` |
| PowerBI | `mcp__powerBI__` | OAuth via `mcp__powerBI__browser_login` |
| M365 (email + calendar) | claude.ai Enterprise built-in — **not in `claude mcp list`** | claude.ai-managed, no OAuth step |
| Slack | claude.ai Enterprise built-in — **not in `claude mcp list`** | claude.ai-managed, no OAuth step |

> **Note:** `mcp__m365-copilot__*` is a separate Copilot AI assistant integration and is **not used by this skill**.

### Optional — auto-installed or degraded gracefully

| Integration | MCP namespace | Auto-install | Fallback if unavailable |
|---|---|---|---|
| **Gong** | `mcp__gong__` | ✅ **Yes** — cloned from [`se-mcp-servers`](https://github.com/clabrado/se-mcp-servers) and registered automatically | SA-7 skipped; `#gong-intelligence` renders muted placeholder |
| LinkedIn | `mcp__linkedin__` | No | WebSearch + WebFetch on public LinkedIn pages |
| SuccessFactors (HR) | `mcp__successFactors__` | No | SF hierarchy + role/territory strategy only |

### Gong auto-install — what happens

When Gong MCP is not registered, the skill installs it automatically before running:

1. Clones/pulls `https://github.com/clabrado/se-mcp-servers` (public)
2. Reads `gong-mcp/README.md` for the registration JSON
3. Runs `claude mcp add-json --scope user gong '<json>'`
4. Calls `mcp__gong__browser_login` (SSO — one browser pop)
5. Verifies auth and proceeds

No manual steps required. If the install fails for any reason, the brief continues without Gong call intelligence.

---

## What it produces

### exec-brief

| Section | Anchor | Content |
|---|---|---|
| **Executive Summary** | `#exec-summary` | 4–5 BLUF bullets naming an account, a number, and an action. HTML adds a 6-tile metric row. |
| **Calendar / Meeting Prep** | `#calendar` | Upcoming customer meetings chronological, each with a prep card: attendees, meeting type, 2–4 prep bullets, and **Gong last-call card** (last call date, themes, open commitments). |
| **Key Accounts** | `#key-accounts` | Top accounts ranked by focus score — why flagged, owning AE + RD, headline numbers. |
| **DT Usage** | `#dt-usage` | Deployment type, health, product footprint per focus account; POC/eval status for prospects. |
| **Struggles** | `#struggles` | Source-cited signals only. Every row requires a citation. Gong `painPoints[]` (verbatim quotes) admitted. Cross-source items flagged ◆ corroborated. |
| **Gong Call Intelligence** | `#gong-intelligence` | Call summaries grouped by account (meeting accounts first): themes, verbatim pain point quotes, open DT commitments. Header: N calls · N accounts · N open commitments. Muted placeholder if Gong not connected. |
| **Consumption** | `#consumption` | PowerBI table: ACV · cons rate (latest/6mo/Δ) · forecast % at end · risk badge. |
| **Opportunities** | `#opportunities` | Open pipeline by RD, top 10 deals, renewals calendar (90d/6mo/12mo). |
| **Public Intelligence** | `#public-intelligence` | DT news + per-company: dated headlines, LinkedIn signals, DT alignment sentence (cited). |
| **Action Items** | `#action-items` | Ranked Critical→Low. Gong `commitments[]` fed in. Each: account · action · horizon · owner. |

### territory-brief

| Section | Content |
|---|---|
| **Territory Summary** | BLUF: health in 4–5 sentences, at-risk count, pipeline total, avg health score |
| **AE Health Table** | Name · accounts · pipeline · renewals · avg health · Gong call count · last call date · risk badge |
| **At-Risk Accounts** | Accounts with ≥2 risk signals (escalation + consumption + no call coverage), grouped by AE |
| **Call Coverage** | Gong gap report: accounts with zero calls in the period, by AE |
| **Open Commitments** | DT-owned Gong commitments across territory, sorted by AE |
| **Pipeline** | Waterfall by RD/AE, renewals calendar, expansion observations |
| **Consumption** | Territory-wide table and heatmap (HTML) |
| **Action Items** | Territory-level coaching and escalation priorities |

---

## How it works

```
Phase -1  MCP Pre-flight     All integrations probed in parallel.
                             Gong auto-installed if missing (clone se-mcp-servers → register → login).
                             Required MCPs block on failure; optional MCPs degrade gracefully.
Phase 0   Parse & Init       Resolves exec name, window, output format, --broad flag, focus context.
Phase 1   Org Discovery      Salesforce → exec User ID → org hierarchy (RDs→AEs) → account footprint →
                             focus-account scoring (capped at 50; meeting accounts always guaranteed).
Phase 2   Parallel Streams   Up to 7 intelligence streams dispatched simultaneously:
                               SA-1  M365 Calendar   — meeting classification + prep flags
                               SA-2  M365 Outlook    — inbox scan, escalations, account threads
                               SA-3  Slack           — exec pass + per-account risk/competitive passes
                               SA-4  Salesforce      — bulk SOQL: opps, cases, contracts, activity, POCs
                               SA-5  PowerBI         — one HTTP call via pbi-extract.py (~3.5s)
                               SA-6  LinkedIn/News   — DT news + per-company public intel
                               SA-7  Gong (optional) — call search → score → top 15 transcripts →
                                                       schema-forced snippet extraction (no full transcripts)
Phase 3   Synthesis          xhigh-effort agent reads merged.json by file path. No live data access.
Phase 4   QA Gate            scripts/qa-check.py (structural + Gong citations) + adversarial agent.
Phase 5   Deliver            Output file + BLUF + top 3 actions to chat.
```

### Key design guarantees

- **No hallucination:** every finding requires a cited source. `dataFound=false` renders only a muted line — never invented content.
- **Gong = snippets only:** SA-7 caps at 15 transcripts and schema-forces extraction to themes, verbatim pain points (≤25 words), commitments, and one key quote. Full transcripts never appear in the brief.
- **Schema-forced subagents:** eliminates ~16% free-text JSON failure rate at scale.
- **Meeting-first:** calendar drives the narrative; meeting accounts are guaranteed in the focus set.
- **Bulk SOQL:** one `WHERE AccountId IN (…)` covers all focus accounts.
- **PowerBI = one HTTP call:** `pbi-extract.py` returns all ~500 org accounts in ~3.5s.
- **Cache-resume:** `--resynthesize` reruns synthesis without repulling any source.

---

## Focus-Account Scoring

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
SKILL.md                   exec-brief full skill specification
territory-brief/SKILL.md   territory-brief full skill specification
scripts/qa-check.py        Scripted QA gate — validates HTML structure, attribution, Gong citations
CLAUDE.md                  MCP pre-flight guide, auto-install instructions, skill install location
exec-brief-overview.pdf    One-page overview for sharing with stakeholders
```

---

## Output location

All output files land in the **current working directory** when the skill is invoked.

- exec-brief: `<exec-slug>-brief-<date>.(html|txt|pdf)`
- territory-brief: `<exec-slug>-territory-<date>.(html|txt)`

---

*Requires claude-work (Claude Enterprise). Maintained by the Dynatrace NORAM SE team.*

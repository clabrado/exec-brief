# exec-brief — CLAUDE.md

## What this repo is

This repository contains the `exec-brief` skill — an executive intelligence briefing tool for
Dynatrace leaders. The skill runs under `claude-work` (Claude Enterprise environment) and is
installed locally at `~/.claude/skills/exec-brief/SKILL.md`.

---

## MCP pre-flight — check before running /exec-brief

This skill requires the following MCPs registered in the Claude environment:

### Required

| MCP | Tool prefix | How to verify |
|---|---|---|
| Salesforce | `mcp__salesforce__` | `mcp__salesforce__run_soql_query("SELECT Id FROM User LIMIT 1")` |
| Salesforce Auth | `mcp__salesforce-auth__` | `mcp__salesforce-auth__token_status()` |
| PowerBI | `mcp__powerBI__` | `mcp__powerBI__token_status()` |
| M365 connector (claude.ai built-in) | `mcp__claude_ai_Microsoft_365__` | Probe directly — will NOT appear in `claude mcp list` |
| Slack connector (claude.ai built-in) | `mcp__claude_ai_Slack__` | Probe directly — will NOT appear in `claude mcp list` |

### Optional (skill degrades gracefully when absent)

| MCP | Tool prefix | Feature enabled |
|---|---|---|
| LinkedIn | `mcp__linkedin__` | LinkedIn company posts and signals (falls back to WebSearch) |
| SuccessFactors | `mcp__successFactors__` | HR org chart (falls back to SF hierarchy) |
| Gong | `mcp__gong__` | SA-7 call intelligence — meeting prep snippets, pain points, open commitments |

### Auto-install from se-mcp-servers

If any MCP is missing, Claude should automatically install it from the public
**se-mcp-servers** repo — no manual steps required for the user:

```
1. Clone or pull https://github.com/clabrado/se-mcp-servers  (public)
2. Point Claude at that directory and say "set up <mcp-name>"
3. The se-mcp-servers CLAUDE.md handles pre-flight, plan-mode approval, and registration
```

For Gong specifically:
```
git clone https://github.com/clabrado/se-mcp-servers ~/Projects/se-mcp-servers
# Then in Claude: "set up gong-mcp" from ~/Projects/se-mcp-servers
# After registration: mcp__gong__browser_login
```

Check registration with `claude mcp list` (local MCPs only; M365 and Slack built-ins are NOT listed).

---

## Using the --broad flag

```
/exec-brief "Nishant Rama" 2w --html           # exec's own Gong calls only (default)
/exec-brief "Nishant Rama" 2w --html --broad   # + all calls with upcoming meeting accounts
```

`--broad` expands SA-7 to search Gong for the top 10 upcoming-meeting accounts, pulling AE
calls for those accounts even if the exec wasn't on the call. Useful for RVPs who want context
on customer conversations their AEs are having. Still capped at 15 transcripts total.

---

## Skill install location

This skill must live at:
```
~/.claude/skills/exec-brief/SKILL.md
```

(or `$CLAUDE_CONFIG_DIR/skills/exec-brief/SKILL.md` if `$CLAUDE_CONFIG_DIR` is set)

**Never write the skill to the project directory or a temp path — it disappears at session end.**

Verify after install:
```bash
ls ~/.claude/skills/exec-brief/SKILL.md
```
Then restart Claude Code or run `/skills` — skills are discovered at startup, not mid-session.

---

## Repository layout

| Path | Purpose |
|---|---|
| `SKILL.md` | The skill definition — copy to `~/.claude/skills/exec-brief/SKILL.md` |
| `scripts/qa-check.py` | Scripted QA gate — run after HTML generation |
| `templates/` | HTML design system for --html output |
| `territory-brief/SKILL.md` | Territory review skill for RDs/RVPs (`/territory-brief`) |
| `CLAUDE.md` | This file |

---

## Security posture

- No credentials committed to this repo
- Auth state lives in `~/.cache/<mcp-name>/` at `0o600`, never in this repo
- Brief output (account names, pipeline, health scores) is **Dynatrace Confidential**
- For external sharing (PDFs, Slack), sanitize customer names — do not share raw brief output

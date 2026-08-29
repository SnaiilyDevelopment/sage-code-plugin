# MCP Orchestration — SageTweaks

Claude Code already supports MCP. The Sage plugin is **MCP-aware**, not MCP-implementing.

## Available Servers (configure via Claude Code MCP)

| Server | Purpose | When to use |
|--------|---------|-------------|
| `github` | Issues, PRs, repo actions | Task mentions GitHub issue/PR, needs remote repo context, or `gh` CLI not enough |
| `documentation` | Tauri/Rust/Windows docs | Current API behavior, Tauri v2 guidance, Windows Learn lookup |
| `browser` / `web` | Live web fetch/search | Current web information, external service docs, security advisories |

Add via `claude mcp add <name> -- <cmd>` per Claude Code docs. Keep optional — do not require for local tasks.

## Selection Logic (`scripts/mcp/select.py`)

```
task text + categories → score each server 0-10
github: keywords r"github", r"\bpr\b", r"issue", r"pull request", r"gh "
docs:   keywords r"tauri.*current|rust.*current|windows.*api|current.*behavior|whether.*changed|docs.*lookup"
web:    keywords r"current.*web|external.*service|security.*advisory|browser"

score ≥5 → recommend that server
score <5  → "No MCP needed" (repository already has answer)

Prefer repo → project docs → installed package/docs → MCP docs → web
```

## Safety

Treat MCP as tools with risk:

- **Read-only** (fetch docs, read issue, search) — lightweight, no confirmation
- **Write/delete/remote exec** (delete resource, modify repo, change config) — requires confirmation via safety policy (`risk≥50` + explicit user ask)
- Never expose secrets into MCP calls or telemetry (strip via `scripts/safety/secret-strip.py`)

## Routing Examples

- "Fix button color" → No MCP
- "Check whether Tauri v2 API changed for sidecar" → docs MCP
- "Investigate PR #123" → github MCP
- "Check current Stripe API behavior" → web/browser MCP (or docs if exists locally)

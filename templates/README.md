# Deployment templates

Canonical building blocks for bringing the other 5 `MCP_*` repos to the same
HTTP-endpoint deployment maturity as this repo. Copy and adapt — see each
sibling repo's own structure before applying a template; the 5 repos are
**not** structurally uniform (verified 2026-08-05, don't assume otherwise):

| Repo | Shape | Root `uv sync` covers everything? |
|---|---|---|
| `MCP_Web_Browser` | Flat single-server (`server.py` + `engine/` at root) | Yes — matches `MCP_Math` almost exactly |
| `MCP_File_System` | True `[tool.uv.workspace]`, 1 member (`servers/fs_basic`) | Yes |
| `MCP_Microsoft_Office` | True `[tool.uv.workspace]`, 11 members, each a nested hatchling package (`servers/docx_basic/docx_basic/server.py`) | Yes |
| `MCP_Data_Analyst` | Monolith root `pyproject.toml` (no real workspace), 9 `servers/<name>/server.py`, reach `shared/` via a `sys.path` hack in `engine.py` | Needs empirical verification — root deps already union all sub-servers' deps, but confirm with a real `uv sync` + run before trusting it |
| `MCP_Machine_Learning` | Same monolith shape as Data_Analyst, 3 sub-servers | Same caveat |

## Files

- `deploy_auth.py` — verbatim copy of `src/shared/deploy_auth.py`. Drop into
  the target repo's `shared/` package as-is (it's already generic, takes an
  env-var `prefix` argument).
- `dockerignore` — copy to `.dockerignore`, adjust the excluded dirs if the
  repo's layout differs (e.g. `servers/` instead of a flat `src/`).
- `tokens.example.json` — copy as-is; update the placeholder names to match
  the client names you'll actually issue tokens to.
- `Dockerfile.single.template` — for flat single-server repos (Web_Browser).
  Placeholders: `{{PKG_NAME}}`, `{{PORT}}`, `{{PREFIX}}`, `{{SRC_COPY_SRC}}`,
  `{{SRC_COPY_DST}}`, `{{RUNTIME_COPY_SRC}}`, `{{RUNTIME_COPY_DST}}`,
  `{{PYTHONPATH}}`, `{{ENTRYPOINT_PATH}}`.
- `Dockerfile.multi.template` — for true-workspace multi-server repos
  (File_System, Office) where one root `uv sync` produces one venv covering
  every sub-server. One image; `SERVER_MODULE` env var picks which
  sub-server's `server.py` a given container runs (see `docker-compose.yml`
  for the one-service-per-sub-server pattern — N services from one image).
  **Verify this same one-`uv sync` approach works for Data_Analyst/ML before
  reusing it there** — their root pyproject is a monolith, not a declared
  workspace, so it needs a live `uv sync` + curl test first (same way HTTP
  transport was verified live for MCP_Math before Docker was built on it).
- `launch_tunnel.sh.template` — remote testing protocol, same idea as
  `azzindani/Folio`'s `launch.sh`. Brings the repo's `docker compose` stack
  up, waits for `/health`, then opens one Cloudflare Quick Tunnel per
  sub-server so it's reachable at a `*.trycloudflare.com` URL from any
  MCP-compatible harness — no VPS, no DNS, no account. Fill in `<REPO_NAME>`,
  `<REPO_SLUG>`, and one `"name:host_port"` entry per sub-server in `PORTS`.
  Ephemeral and unauthenticated at the transport level — always pair with a
  bearer token (`<PREFIX>_API_KEY` / `_TOKENS_FILE`) before tunneling, and
  never use it as a substitute for a real TLS-terminated deployment.

## What every sibling repo needs (regardless of shape)

1. `--transport {stdio,http} --host --port` argparse in each `server.py`,
   reading `<PREFIX>_TRANSPORT` / `<PREFIX>_HOST` / `<PREFIX>_PORT` env vars
   as defaults — copy the pattern from `MCP_Math/src/server.py::main()`.
2. `mcp = FastMCP(..., host=..., port=..., token_verifier=..., auth=...)` from
   `mcp.server.fastmcp`, built via `build_auth("<PREFIX>", host, port, bridge)` +
   `@mcp.custom_route("/health", ...)` / `/version` — copy the pattern from
   `MCP_Math/src/server.py` (top of file).
3. A Dockerfile + `docker-compose.yml` built from the matching template above
   — **build and run it, curl `/health` and `/mcp` with/without a token,
   before considering the repo done.** Don't ship an unverified Dockerfile.
4. A `docker-ghcr-publish` job in `release.yml`, gated behind a
   `workflow_dispatch` boolean so a tag publishes nothing by default, calling
   `azzindani/MCP_Math/.github/actions/docker-ghcr-publish@main` and
   `.../setup-uv-python@main` — see `MCP_Math/.github/workflows/*.yml` for the
   exact call shape. Do **not** add a no-push `docker-build` job to `ci.yml`:
   the `e2e` job already builds the image (`docker compose up --build`) from
   the same context and then runs it, so a build-only job cannot fail without
   `e2e` failing first and only costs a second image build per push.

# math-mcp-server

A self-hosted MCP server that offloads all mathematical computation from a local LLM to a deterministic Python engine. Eliminates arithmetic and formula evaluation errors in local models (Qwen, Gemma, Llama, etc.) by making the LLM a dispatcher and the server the sole executor of all numeric operations.

## Features

* **8 tools** across arithmetic, algebra, statistics, and LaTeX formula evaluation — no cloud, no API keys, no GPU required
* **AST-validated expression evaluator** — never uses `eval()` or `exec()`; all expressions are parsed by SymPy and walked by a whitelist before execution
* **Symbolic algebra** — solve equations, simplify expressions, differentiate and integrate via SymPy
* **Unit conversion** — fully local via Pint; handles 1 000+ physical units including temperatures, currencies of measure, and compound units
* **Descriptive statistics** — count, mean, median, std, Q1/Q3, skewness, kurtosis via NumPy + SciPy
* **LaTeX formula execution** — 6-stage internal pipeline: parse → validate → resolve deps → substitute → evaluate → format
* **Cross-platform timeout** — `signal.alarm` on Unix, `threading.Timer` on Windows; no expression can hang the server
* **Constrained mode** — reduces dataset size limits for lower-memory machines via `MCP_CONSTRAINED_MODE=1`
* **Modular architecture** — engine split into focused sub-modules, all under 1 000 lines
* **Zero data leaves the machine** — works fully offline after install

## Important: Expression Syntax Only

> **Do not describe math problems in plain English and expect the model to pass them to the tools directly.**
>
> The MCP tools accept **exact expression strings**, not natural language. The model must translate your request into a valid expression before calling a tool.
>
> Always tell the model what you want in precise terms:
>
>     What is the derivative of x**3 + 2*x with respect to x?
>     Evaluate the LaTeX formula \frac{a}{b} where a=10 and b=4.
>
> The model will construct the correct expression string and call the appropriate tool. Vague requests like "solve my quadratic" without providing the expression will produce incorrect or empty results.

## Quick Install (LM Studio)

1. Open LM Studio → **Developer** tab (`</>` icon) or find it via **Integrations**
2. Find **mcp.json** or **Edit mcp.json** → click to open
3. Paste the config for your platform (see below)
4. Wait for the green dot next to **math**
5. Start chatting — the model will see all 8 math tools

### Windows

```json
{
  "mcpServers": {
    "math": {
      "command": "powershell",
      "args": [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "$d = Join-Path $env:USERPROFILE '.mcp_servers\\math-mcp-server'; $g = Join-Path $d '.git'; if (!(Test-Path $g)) { if (Test-Path $d) { Remove-Item -Recurse -Force $d }; git clone https://github.com/azzindani/mcp_math.git $d --quiet } else { Set-Location $d; git fetch origin --quiet; git reset --hard FETCH_HEAD --quiet }; Set-Location $d; uv sync --quiet; $env:PYTHONPATH='src'; uv run python src/server.py"
      ],
      "env": { "MCP_CONSTRAINED_MODE": "0" },
      "timeout": 600000
    }
  }
}
```

### macOS / Linux

```json
{
  "mcpServers": {
    "math": {
      "command": "bash",
      "args": [
        "-c",
        "d=\"$HOME/.mcp_servers/math-mcp-server\"; if [ ! -d \"$d/.git\" ]; then rm -rf \"$d\"; git clone https://github.com/azzindani/mcp_math.git \"$d\" --quiet; else cd \"$d\" && git fetch origin --quiet && git reset --hard FETCH_HEAD --quiet; fi; cd \"$d\"; uv sync --quiet; PYTHONPATH=src uv run python src/server.py"
      ],
      "env": { "MCP_CONSTRAINED_MODE": "0" },
      "timeout": 600000
    }
  }
}
```

## Requirements

* **Git** — `git --version`
* **Python 3.12** — `python --version`
* **uv** — `uv --version` ([install guide](https://docs.astral.sh/uv/getting-started/installation/))
* **LM Studio** with a model that supports tool calling (Qwen3, Gemma4, etc.)

## Platform Support

| Platform | Status |
|---|---|
| Windows | Tested — real-world verified (Windows 11) |
| macOS | Untested — CI/CD pipeline passes |
| Linux | Untested — CI/CD pipeline passes |

> Real-world usage has only been verified on Windows. macOS and Linux are supported by design and pass the automated CI pipeline, but have not been tested by hand. Reports from non-Windows users are welcome.

## First Run

> **Pre-install recommended:** To avoid the 60-second LM Studio connection timeout on first launch, run this once in PowerShell before connecting:
>
> ```powershell
> $d = Join-Path $env:USERPROFILE '.mcp_servers\math-mcp-server'
> $g = Join-Path $d '.git'
> if (!(Test-Path $g)) { if (Test-Path $d) { Remove-Item -Recurse -Force $d }; git clone https://github.com/azzindani/mcp_math.git $d --quiet }
> Set-Location $d; uv sync
> ```
>
> If you skip this step and LM Studio times out, press **Restart** in the MCP Servers panel — it will reconnect and complete the install immediately.

### Steps

1. Paste the mcp.json config above and save
2. LM Studio will launch the server and install all Python dependencies on first connect (2–3 minutes)
3. A green dot next to **math** confirms the server is ready
4. Send any message — the model now has access to all 8 tools

## Available Tools

All 8 tools are read-only pure functions. Input → output, nothing persisted.

### Arithmetic (2 tools)

| Tool | Purpose |
|---|---|
| `calculate` | Evaluate any numeric expression: `sqrt(144)`, `2**32`, `sin(pi/6)` — AST-validated, no `eval()` |
| `convert_units` | Convert between physical units: length, mass, temperature, speed, pressure, and more |

### Algebra (4 tools)

| Tool | Purpose |
|---|---|
| `solve` | Solve equations for a variable: `x**2 - 4 = 0` → `[-2, 2]` |
| `simplify` | Simplify algebraic expressions: `sin(x)**2 + cos(x)**2` → `1` |
| `diff` | Differentiate expressions: `diff("x**3", "x", order=2)` → `6*x` |
| `integrate` | Definite or indefinite integrals: `integrate("x**2", "x", "0", "3")` → `9` |

### Statistics (1 tool)

| Tool | Purpose |
|---|---|
| `describe` | Descriptive statistics for a numeric list: count, mean, median, std, min, max, Q1, Q3, skewness, kurtosis |

### LaTeX (1 tool)

| Tool | Purpose |
|---|---|
| `eval_latex` | Execute a LaTeX formula with variable substitution — full 6-stage pipeline (parse → validate → resolve → substitute → evaluate → format) |

#### `eval_latex` pipeline stages

| Stage | Action |
|---|---|
| 1 — Parse | `latex2sympy2` converts LaTeX string to SymPy expression tree |
| 2 — Validate | AST whitelist check — raises `UnsafeExpressionError` on any non-math node |
| 3 — Resolve deps | Topological sort of sub-formula dependencies (skipped when all variables are plain floats) |
| 4 — Substitute | `sympy.subs()` replaces variable symbols with provided values |
| 5 — Evaluate | `evaluate_with_timeout()` calls `evalf(15)` with a 5-second cross-platform timeout |
| 6 — Format | `formatter.py` converts result to JSON-safe float/int and attaches `token_estimate` |

## Usage Examples

1. **Basic arithmetic**: "What is 2 to the power of 32?"

2. **Square root and trig**: "Calculate sqrt(2) multiplied by sqrt(8)"

3. **Unit conversion**: "Convert 100 kilometers to miles"

4. **Temperature conversion**: "Convert 0 degrees Celsius to Kelvin"

5. **Solve a quadratic**: "Solve x squared minus 4 equals zero"

6. **Solve with equals sign**: "Find x where x + 3 = 7"

7. **Simplify a trig identity**: "Simplify sin(x)^2 + cos(x)^2"

8. **Differentiate**: "Find the derivative of x^3 + 2x with respect to x"

9. **Second-order derivative**: "Find the second derivative of x^3"

10. **Definite integral**: "Integrate x^2 from 0 to 3"

11. **Indefinite integral**: "Find the antiderivative of cos(x)"

12. **Descriptive statistics**: "Give me descriptive statistics for this dataset: 4, 7, 13, 2, 1, 9, 10"

13. **LaTeX fraction**: "Evaluate the LaTeX formula \\frac{a}{b} where a is 10 and b is 4"

14. **LaTeX Pythagorean theorem**: "Evaluate \\sqrt{a^{2} + b^{2}} with a=3 and b=4"

15. **Kinetic energy formula**: "Compute \\frac{1}{2} m v^{2} where m=10 and v=6"

## Deployment

| Mode | Best for | Transport | Auth |
|---|---|---|---|
| **Local stdio** (default, above) | LM Studio / Claude Code on your machine | stdio | none |
| **Local Docker / HTTP** | Testing, or one other machine on your LAN | HTTP on a port | optional |
| **VPS Docker** | Remote MCP clients (claude.ai, hosted harnesses) | HTTP on a port | **required** |

### HTTP transport (no Docker)

```bash
uv run python src/server.py --transport http --host 0.0.0.0 --port 8765
curl http://localhost:8765/health   # {"status":"ok","version":"0.1.0"}
```

### Docker

```bash
docker compose up -d --build
curl http://localhost:8765/health
```

With auth (**required** for any publicly reachable deploy — this is how the
production `math.casava.space` endpoint runs):

```bash
echo "MATH_API_KEY=$(openssl rand -hex 24)" > .env   # gitignored, auto-loaded by docker-compose.yml
docker compose up -d --build
```

For multiple named clients instead of one shared key (Folio-style):

```bash
cp tokens.example.json tokens.json   # edit: replace placeholders with `openssl rand -hex 32`
MATH_TOKENS_FILE=/home/math/tokens.json docker compose up -d --build
```

`/mcp` requires `Authorization: Bearer <token>` once any of `MATH_TOKENS_FILE` /
`MATH_TOKENS` / `MATH_API_KEY` is set; `/health` and `/version` stay unauthenticated.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `MATH_TRANSPORT` | `stdio` | `stdio` or `http` |
| `MATH_HOST` | `127.0.0.1` | Bind address for HTTP mode |
| `MATH_PORT` | `8765` | Port for HTTP mode |
| `MATH_TOKENS_FILE` | unset | JSON file of named bearer tokens (`{"name": "token"}`) — highest priority |
| `MATH_TOKENS` | unset | Inline `"name:token,name2:token2"` |
| `MATH_API_KEY` | unset | Single shared bearer token |
| `MCP_CONSTRAINED_MODE` | `0` | Set to `1` to tighten dataset size limits for low-memory machines (max dataset: 100 rows vs 10 000) |

### Remote testing (Cloudflare Quick Tunnel)

Same idea as `azzindani/Folio`'s `launch.sh`: bring the Docker deployment up
and expose it at an ephemeral `*.trycloudflare.com` URL — no VPS, no DNS, no
account — so it's reachable from any MCP-compatible harness for a quick
remote smoke test.

```bash
./launch_tunnel.sh          # docker compose up -d --build, then tunnel
./launch_tunnel.sh stop     # tear the tunnel down (containers keep running)
```

Not for production: Quick Tunnels are unauthenticated at the transport layer.
Set `MATH_API_KEY` or `MATH_TOKENS_FILE` before tunneling so `/mcp` still
requires a bearer token even while it's publicly reachable.

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_CONSTRAINED_MODE` | `0` | Set to `1` to tighten dataset size limits for low-memory machines (max dataset: 100 rows vs 10 000) |

## Uninstall

**Step 1:** Remove from LM Studio

1. Open LM Studio → Developer tab (`</>`)
2. Delete the `math` entry from MCP Servers
3. Restart LM Studio

**Step 2:** Delete installed files

Windows:
```
rmdir /s /q %USERPROFILE%\.mcp_servers\math-mcp-server
```

macOS / Linux:
```bash
rm -rf ~/.mcp_servers/math-mcp-server
```

## Architecture

```
math-mcp-server/
├── src/
│   ├── server.py              ← MCP entry point — thin wrappers only (zero domain logic)
│   ├── _math_helpers.py       ← shared imports, constants, _error() helper
│   ├── _math_arithmetic.py    ← calculate(), convert_units()
│   ├── _math_algebra.py       ← solve(), simplify(), diff(), integrate()
│   ├── _math_statistics.py    ← describe(), regression() (regression is internal only)
│   ├── _math_latex.py         ← eval_latex() — full 6-stage pipeline
│   ├── engine/
│   │   ├── __init__.py        ← thin router + re-exports all tool functions
│   │   ├── sandbox.py         ← AST whitelist + cross-platform timeout
│   │   ├── deps.py            ← DAG builder + topological sort
│   │   └── formatter.py       ← structured JSON output builder
│   └── shared/
│       ├── platform_utils.py  ← is_constrained_mode(), get_max_*() helpers
│       └── progress.py        ← ok(), fail(), info(), warn() helpers
├── tests/
│   ├── fixtures/
│   │   ├── simple_formulas.json
│   │   └── messy_latex.json
│   └── test_engine.py         ← 74 tests: happy path, sandbox rejection, timeout, constrained mode
├── install/
│   ├── install.sh             ← macOS / Linux installer
│   └── install.bat            ← Windows installer
├── pyproject.toml
├── uv.lock
├── .python-version            ← pins Python 3.12
├── .gitattributes
├── verify_tool_docstrings.py  ← CI gate: all @mcp.tool() docstrings ≤ 80 chars
└── README.md
```

No `eval()`. No `exec()`. No network calls. No state. Pure functions.

## Development

### Local Testing

```bash
# Install all dependencies
uv sync

# Run all 74 tests
PYTHONPATH=src uv run pytest tests/ -q --tb=short

# Run in constrained mode
MCP_CONSTRAINED_MODE=1 PYTHONPATH=src uv run pytest tests/ -q --tb=short

# Full CI sequence: lint → verify docstrings → test
PYTHONPATH=src uv run ruff check src/
uv run python tests/verify_tool_docstrings.py
PYTHONPATH=src uv run pytest tests/ -q --tb=short
```

### Run the Server Locally

```bash
# stdio transport (default — for LM Studio)
PYTHONPATH=src uv run python src/server.py

# HTTP transport (for testing with curl or a browser client)
PYTHONPATH=src uv run python src/server.py --transport http --port 8765
```

## License

MIT

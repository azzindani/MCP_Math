# CLAUDE.md — Math MCP Server

> AI coding agent instructions. Follow every rule in this file exactly.
> When this file conflicts with the general STANDARDS.md, this file takes precedence.
> Standards reference: https://github.com/azzindani/Standards/blob/main/local_mcp/STANDARDS.md

---

## 1. Project Overview

**math-mcp-server** is a self-hosted MCP server that offloads all mathematical
computation from a local LLM to a deterministic Python engine. Local models
(Qwen3.5 4B/9B, Gemma 4 E4B) are unreliable at arithmetic and formula evaluation.
This server eliminates that failure by making the LLM a dispatcher and the server
the sole executor of all numeric operations.

**Core capabilities:**
- Safe arithmetic expression evaluation (no `eval()` — AST-validated)
- Unit conversion (Pint, fully local)
- Symbolic algebra: solve, simplify, differentiate, integrate (SymPy)
- Descriptive statistics and regression (NumPy, SciPy)
- Custom LaTeX formula execution (latex2sympy2 → SymPy → numeric result)

**Founding constraints (non-negotiable):**
- All execution on local CPU — no GPU required, no cloud APIs, no network at runtime
- Zero data leaves the machine
- No API keys, no OAuth, no subscriptions
- Works fully offline after install

**Deployment scope:** local-first is the default and the constraints above always
hold for the computation itself — no tool ever calls out to a cloud API to produce
a result. On top of that, this server can also run in HTTP mode, self-hosted behind
a reverse proxy, so it can be connected as a remote endpoint by AI platforms and
harnesses (Claude Desktop, claude.ai remote MCP, other MCP clients) rather than only
as a local stdio process. Remote mode is opt-in, bearer-token authenticated (see §11),
and still runs on infrastructure you control — self-hosted, not a third-party service.
This is one of six sibling `MCP_*` repos brought to this same deployment model.

**Target hardware:** 8 GB VRAM, 9B local model (Q3_K_S / Q4_K_M), ~10,000–12,000 token context

**Tier:** Basic (single-tier server — math is inherently a single-tier domain)

---

## 2. Repository Structure

```
math-mcp-server/
├── src/
│   ├── server.py              ← MCP entry point, thin wrappers only
│   ├── _math_helpers.py       ← shared imports, constants, _error helper
│   ├── _math_arithmetic.py    ← calculate(), convert_units()
│   ├── _math_algebra.py       ← solve(), simplify(), diff(), integrate()
│   ├── _math_statistics.py    ← describe(), regression()
│   ├── _math_latex.py         ← eval_latex() — full 6-stage pipeline
│   ├── engine/
│   │   ├── __init__.py        ← thin router, re-exports all tool functions
│   │   ├── sandbox.py         ← AST whitelist + cross-platform timeout
│   │   ├── deps.py            ← DAG builder + topological sort
│   │   └── formatter.py       ← structured JSON output builder
│   └── shared/
│       ├── __init__.py
│       ├── platform_utils.py  ← is_constrained_mode(), get_max_*() helpers
│       └── progress.py        ← ok(), fail(), info(), warn() helpers
├── tests/
│   ├── fixtures/
│   │   ├── simple_formulas.json
│   │   └── messy_latex.json
│   └── test_engine.py
├── install/
│   ├── install.sh
│   └── install.bat
├── pyproject.toml
├── uv.lock
├── .python-version
├── .gitattributes
├── CLAUDE.md                  ← this file
└── README.md
```

**File size hard limits (from STANDARDS.md §15):**

| File | Target | Hard limit |
|---|---|---|
| `server.py` | 80–120 lines | 300 lines |
| `engine.py` (thin router) | 30–50 lines | 1,000 lines |
| `_math_helpers.py` | 100–200 lines | 1,000 lines |
| `_math_*.py` sub-modules | 100–300 lines | 1,000 lines |
| `engine/sandbox.py` | 80–150 lines | 1,000 lines |
| `engine/deps.py` | 60–120 lines | 1,000 lines |
| `engine/formatter.py` | 60–100 lines | 1,000 lines |

---

## 3. Tool Inventory

**Total: 8 tools** — within the 8-tool target for 8 GB VRAM / 9B model.

| Tool | Module | Type | Description |
|---|---|---|---|
| `calculate` | `_math_arithmetic.py` | Tier 1 read | Safe arithmetic expression evaluator |
| `convert_units` | `_math_arithmetic.py` | Tier 1 read | Unit conversion via Pint |
| `solve` | `_math_algebra.py` | Tier 1 read | Symbolic equation solver |
| `simplify` | `_math_algebra.py` | Tier 1 read | Algebraic simplification |
| `diff` | `_math_algebra.py` | Tier 1 read | Differentiation |
| `integrate` | `_math_algebra.py` | Tier 1 read | Definite/indefinite integration |
| `describe` | `_math_statistics.py` | Tier 1 read | Descriptive statistics on a dataset |
| `eval_latex` | `_math_latex.py` | Tier 1 read | Custom LaTeX formula execution |

All 8 tools are **read-only** (no persistent state modified, no files written).
No snapshot, no backup, no receipt log required — math tools are pure functions.

**No additional tools may be added without reducing another tool first.**
The 8-tool limit is a hard constraint for the 8 GB hardware target.

---

## 4. Architecture Principles

### 4.1 Engine / server split (STANDARDS.md §14)

`server.py` contains zero domain logic. Every `@mcp.tool()` body is a single line:

```python
return engine.calculate(expression)
```

`engine.py` contains zero MCP imports. It is a thin router that re-exports from
sub-modules. All real logic lives in `_math_*.py` sub-modules and `engine/`.

### 4.2 Sub-module pattern (STANDARDS.md §15)

Sub-modules are prefixed `_math_` to avoid collision.
Sub-modules have zero MCP imports — same rule as `engine.py`.
`engine.py` is the only file tests import from.

### 4.3 No state, no snapshots

Math tools are pure functions. Input → output, nothing persisted.
No `.mcp_versions/`, no receipt log, no companion state files needed.
This is the explicit exception for this domain: STANDARDS.md §19 snapshot rule
applies only to tools that modify persistent data.

### 4.4 Internal pipeline, not handover protocol

Multi-step computation (especially in `eval_latex`) happens inside the tool,
not across multiple LLM-orchestrated tool calls.

The LLM chains tool calls only when genuine reasoning is needed between steps
(e.g., `solve()` → interpret result → `eval_latex()` to substitute numerically).
Mechanical transformation steps (parse → validate → substitute → evaluate) are
internal pipeline stages invisible to the LLM.

### 4.5 Self-hosted execution (STANDARDS.md §4)

Every tool must answer "yes" to: **can this run with the machine offline?**

No tool may call an external API, require a network connection at runtime,
or depend on a cloud service. All computation is local CPU only.

### 4.6 Safety: no eval(), no exec() (STANDARDS.md §18 + §36 rule 17)

The `calculate()` tool and `eval_latex()` pipeline must never pass user strings
to Python's `eval()` or `exec()`. All expression strings are parsed by SymPy's
`sympify()` or `latex2sympy2`, then walked by `engine/sandbox.py`'s AST whitelist
before any evaluation occurs.

---

---

## 5. Tool Schema Design (STANDARDS.md §11)

### Docstring rule: ≤ 80 characters, machine-readable

```python
# Good
"""Evaluate arithmetic expression. Returns numeric result and steps."""  # 62 chars

# Bad
"""This tool evaluates a mathematical arithmetic expression provided as a string
and returns the computed numeric result along with intermediate steps."""  # 144 chars
```

CI enforces this via `verify_tool_docstrings.py`. Any docstring over 80 chars fails the build.

### Parameter types — only these are permitted

- `str` — expression strings, variable names, unit strings, formula strings
- `int` — precision digits, max_results
- `float` — numeric variable values when passed individually
- `bool` — flags
- `dict[str, float]` — variable substitution maps for `eval_latex`
- `list[float]` — numeric datasets for `describe` and `regression`

Never use `Optional[T]`, `Union`, `Any`, `Enum`, `dict` (untyped), custom Pydantic.

### Tool annotations (STANDARDS.md §12)

All 8 tools are read-only pure functions:

```python
@mcp.tool(annotations={
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
})
```

---

## 6. Engine Sub-Module Design

### 6.1 `_math_helpers.py`

Centralizes all shared imports, constants, and the private `_error()` helper.
Contents: all third-party imports (sympy, numpy, scipy, pint, latex2sympy2),
`ALLOWED_SYMPY_NODES` set, `_error(op, msg, hint)` → dict helper, `__all__`.

### 6.2 `_math_arithmetic.py`

`calculate(expression: str) → dict`
- Parse with `sympify()` → validate AST → evaluate with timeout
- Returns: `{success, op, result, expression_parsed, steps, token_estimate}`

`convert_units(value: float, from_unit: str, to_unit: str) → dict`
- Uses `pint.UnitRegistry()` — fully local
- Returns: `{success, op, result, from, to, token_estimate}`

### 6.3 `_math_algebra.py`

`solve(equation: str, variable: str = "x") → dict` — `sympy.solve()`
`simplify(expression: str) → dict` — `sympy.simplify()`
`diff(expression: str, variable: str = "x", order: int = 1) → dict` — `sympy.diff()`
`integrate(expression: str, variable: str = "x", lower: str = "", upper: str = "") → dict` — `sympy.integrate()`

### 6.4 `_math_statistics.py`

`describe(dataset: list[float]) → dict` — numpy + scipy.stats
Returns: count, mean, median, std, min, max, q1, q3, skewness, kurtosis, token_estimate

`regression(x: list[float], y: list[float], degree: int = 1) → dict` — numpy.polyfit()
Returns: coefficients, r_squared, degree, equation, token_estimate

### 6.5 `_math_latex.py` — 6-stage internal pipeline

```
Stage 1: parse        latex2sympy2 → SymPy expression tree
Stage 2: validate     sandbox.py AST whitelist — raises on unsafe node
Stage 3: resolve_deps deps.py topological sort (only if sub-formulas exist)
Stage 4: substitute   sympy .subs() with variable dict
Stage 5: evaluate     sandbox.py evaluate_with_timeout() → evalf(15)
Stage 6: format       formatter.py → structured JSON
```

`eval_latex(formula: str, variables: dict[str, float] = {}) → dict`
Returns: `{success, op, result, formula_parsed, substitutions, steps[], token_estimate}`

### 6.6 `engine/sandbox.py`

1. `validate_ast(expr)` — walks SymPy tree, raises `UnsafeExpressionError` on non-math nodes
2. `evaluate_with_timeout(expr, timeout=5)` — cross-platform timeout (signal.alarm on Unix, threading.Timer on Windows)

### 6.7 `engine/deps.py`

DAG builder + topological sort. Used only by `_math_latex.py` when variables dict
contains string sub-formulas (not plain floats). Skipped in the common case.

### 6.8 `engine/formatter.py`

Single responsibility: convert raw SymPy result + metadata → standard response dict
including `token_estimate = len(str(response)) // 4`.

---

## 7. Return Value Contract (STANDARDS.md §16)

Every tool returns a `dict`. No exceptions. No plain strings, lists, None, or bool.

### Required fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `success` | `bool` | Always | First key checked by LLM |
| `op` | `str` | Always | Operation name |
| `result` | varies | On success | Computed value (float, str, list) |
| `error` | `str` | On failure | Human-readable description |
| `hint` | `str` | On failure | Actionable recovery instruction |
| `progress` | `list` | Always | Execution log entries |
| `token_estimate` | `int` | Always | `len(str(response)) // 4` |

No `backup`, `dry_run`, or `truncated` fields — math tools are stateless read operations.

---

## 8. Error Handling Contract (STANDARDS.md §17)

All exceptions caught in engine sub-modules. None propagate to `server.py`.
Every error dict has `success: False`, `op`, `error`, `hint`, `token_estimate`.

Hint rules: must name a specific tool or fix. Never "Invalid input." or "Try again."

```python
# Good hints
"hint": "Use solve() for equations with unknowns. calculate() handles numeric expressions."
"hint": "Check unit names: pint.readthedocs.io/en/stable/user/units.html"
"hint": "Simplify the expression or split into smaller parts."
```

---

## 9. Token Budget (STANDARDS.md §20)

Per-response targets: calculate ≤80, convert_units ≤60, solve ≤150,
simplify ≤100, diff ≤100, integrate ≤120, describe ≤200, eval_latex ≤250.

Always call `get_max_results()` / `is_constrained_mode()` from `shared/platform_utils.py`.
Never hardcode limits. `MCP_CONSTRAINED_MODE=1` tightens dataset size limits.

---

## 10. Python / Tooling Standards (STANDARDS.md §5)

- Python `3.12` — pin `requires-python = "==3.12.*"`
- Package manager: `uv` only
- Linting + formatting: `ruff` only
- Type checking: `pyright`
- Testing: `pytest`
- FastMCP: pin `fastmcp>=2.0,<3.0`

```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP"]
ignore = ["E402"]
```

---

## 11. Transport and Install (STANDARDS.md §30, §31)

Server supports `--transport stdio` (default) and `--transport http --port 8765`.
Install path: `~/.mcp_servers/math-mcp-server` on all platforms.
mcp.json uses PowerShell on Windows, bash on macOS/Linux.
Clone guard checks `.git` subfolder. Update via `git fetch + git reset --hard FETCH_HEAD`.
Env var: `MCP_CONSTRAINED_MODE` (never project-specific name). Timeout: `600000`.

For Docker/remote deployment — connecting this server to AI platforms and harnesses
as a hosted endpoint, not just a local stdio process — bearer auth
(`src/shared/deploy_auth.py`, `build_token_verifier("MATH")`) gates the whole server:

- `MATH_TOKENS_FILE` (named tokens, JSON `{name: token}`) — highest priority
- `MATH_TOKENS` (inline `"name:token,name2:token2"`)
- `MATH_API_KEY` (single shared token)
- unset = open mode (no auth) — localhost/private-network use only, never for a
  publicly reachable deployment

The production deployment runs `MATH_API_KEY` set from a local `.env` file
(gitignored, never committed) behind a reverse proxy; a request without a valid
`Authorization: Bearer <token>` header is rejected with `401` before it reaches
any tool.

---

## 12. Testing Standards (STANDARDS.md §27)

Tests import `engine.py` directly — never spin up an MCP process.

Required per tool: happy path, malformed input, unsafe input (sandbox rejection),
timeout, constrained mode, token_estimate present.

Coverage: `shared/` 100%, `engine/*.py` 90%, `_math_*.py` 90%.

CI runs on `ubuntu-22.04`, `macos-latest`, `windows-latest` with `fail-fast: false`.
`PYTHONPATH: "."` and `MCP_CONSTRAINED_MODE: "1"` set in CI env.
No `brew install libomp` needed (no XGBoost/LightGBM in this project).

### Remote smoke tests (not part of pytest / CI)

`pytest` never spins up an MCP process or touches the network — that's
deliberate (STANDARDS.md offline-first testing). Verifying the deployed HTTP
endpoint (auth enforcement, real tool calls over the real public domain) is a
separate, manual/on-demand check: hand-authored `curl` sessions or a
`remote_smoke_test.sh` script run after `docker compose up`, never wired into
CI, and never storing the live API key in the repo. This is how the
Office consolidation's `Invalid Host header` regression (DNS-rebinding
protection rejecting the public reverse-proxy hostname) was actually caught —
`pytest` alone could not have found it.

---

## 13. What the AI Must Never Do

Beyond STANDARDS.md §36 prohibitions, for this project:

1. Never use `eval()` or `exec()` — use SymPy parsing + AST validation only
2. Never add a 9th tool without removing another
3. Never make pipeline stages (parse, validate, substitute, evaluate) into separate MCP tools
4. Never return raw SymPy objects in JSON — always convert to `str` or `float`
5. Never print to stdout — use `logging` to stderr
6. Never hardcode numeric limits — use `shared/platform_utils.py` helpers
7. Never use `signal.alarm` on Windows — use `threading.Timer` instead
8. Never import MCP/FastMCP outside `server.py`
9. Never write business logic in `server.py` — tool bodies are one line each
10. Never skip `validate_ast()` before any `evalf()` call

---

## 14. Progress Tracker

### Phase 1 — Setup
- [x] `pyproject.toml` with pinned versions
- [x] `.python-version` = `3.12`
- [x] `.gitattributes` with `* text=auto eol=lf`
- [x] `uv sync` — no errors
- [x] `shared/platform_utils.py`
- [x] `shared/progress.py`

### Phase 2 — Engine core
- [x] `engine/__init__.py` (thin router — merged here since `engine/` package takes precedence over `engine.py`)
- [x] `engine/sandbox.py` (AST whitelist + cross-platform timeout)
- [x] `engine/deps.py` (DAG + topological sort)
- [x] `engine/formatter.py` (structured JSON builder)
- [x] `_math_helpers.py` (shared imports + `_error()`)

### Phase 3 — Tool sub-modules
- [x] `_math_arithmetic.py` — `calculate`, `convert_units`
- [x] `_math_algebra.py` — `solve`, `simplify`, `diff`, `integrate`
- [x] `_math_statistics.py` — `describe`, `regression` (regression is engine-only; not exposed as MCP tool)
- [x] `_math_latex.py` — `eval_latex` 6-stage pipeline

### Phase 4 — Router and server
- [x] `engine/__init__.py` thin router (`__all__` + imports) — note: `engine.py` cannot coexist with `engine/` package; router lives in `engine/__init__.py`
- [x] `server.py` (8 one-liner `@mcp.tool()` wrappers — exactly 8 tools per spec)
- [x] All docstrings ≤ 80 chars verified (`verify_tool_docstrings.py`)

### Phase 5 — Tests
- [x] `tests/fixtures/simple_formulas.json`
- [x] `tests/fixtures/messy_latex.json`
- [x] `tests/test_engine.py` (happy path, malformed, unsafe/sandbox rejection, timeout, constrained mode, token_estimate)
- [x] `uv run pytest` — 74 tests, all pass
- [x] `MCP_CONSTRAINED_MODE=1 uv run pytest` — limits enforced

### Phase 6 — CI/CD and distribution
- [x] `.github/workflows/ci.yml`
- [x] `.github/workflows/release.yml`
- [x] `verify_tool_docstrings.py`
- [x] `install/install.sh` and `install/install.bat`
- [x] `README.md` with install, usage examples, mcp.json config, architecture
- [ ] CI passes on all 3 platforms — pending GitHub Actions run
- [ ] Manual test in LM Studio (9B model) — requires local hardware

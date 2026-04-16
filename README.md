# math-mcp-server

A self-hosted MCP server that offloads all mathematical computation from a local LLM to a deterministic Python engine. Eliminates arithmetic and formula evaluation errors in local models (Qwen, Gemma, Llama, etc.) by making the LLM a dispatcher and the server the sole executor of all numeric operations.

---

## What it does

Exposes 8 pure-function tools over MCP (stdio or HTTP):

| Tool | Description |
|---|---|
| `calculate` | Safe arithmetic expression evaluator (AST-validated, no `eval()`) |
| `convert_units` | Unit conversion via Pint (fully local) |
| `solve` | Symbolic equation solver (SymPy) |
| `simplify` | Algebraic simplification (SymPy) |
| `diff` | Differentiation (SymPy) |
| `integrate` | Definite / indefinite integration (SymPy) |
| `describe` | Descriptive statistics (NumPy + SciPy) |
| `eval_latex` | LaTeX formula execution — 6-stage internal pipeline |

**Founding constraints:**
- All execution on local CPU — no GPU, no cloud, no network at runtime
- Zero data leaves the machine
- No API keys, no OAuth
- Works fully offline after install

---

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (package manager)
- 8 GB RAM recommended (no GPU required)

---

## Installation

### macOS / Linux

```bash
curl -LsSf https://raw.githubusercontent.com/azzindani/mcp_math/main/install/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/azzindani/mcp_math.git ~/.mcp_servers/math-mcp-server
cd ~/.mcp_servers/math-mcp-server
uv sync
```

### Windows

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/azzindani/mcp_math/main/install/install.bat" -OutFile install.bat
.\install.bat
```

---

## mcp.json configuration

### macOS / Linux

```json
{
  "math-mcp-server": {
    "command": "bash",
    "args": ["-c", "cd ~/.mcp_servers/math-mcp-server && uv run python server.py --transport stdio"],
    "timeout": 600000
  }
}
```

### Windows

```json
{
  "math-mcp-server": {
    "command": "powershell",
    "args": ["-Command", "cd $env:USERPROFILE\\.mcp_servers\\math-mcp-server; uv run python server.py --transport stdio"],
    "timeout": 600000
  }
}
```

---

## Usage examples

### Arithmetic

```
calculate("2 ** 32")           → 4294967296
calculate("sqrt(2) * sqrt(8)") → 4.0
```

### Unit conversion

```
convert_units(100, "kilometer", "mile")   → 62.137...
convert_units(0, "degC", "kelvin")        → 273.15
```

### Algebra

```
solve("x**2 - 4", "x")           → ["-2", "2"]
simplify("sin(x)**2 + cos(x)**2") → "1"
diff("x**3 + 2*x", "x")          → "3*x**2 + 2"
integrate("x**2", "x", "0", "3") → "9"
```

### Statistics

```
describe([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
→ {mean: 5.5, std: 3.027..., median: 5.5, ...}

regression([0,1,2,3], [0,2,4,6], degree=1)
→ {coefficients: [2.0, 0.0], r_squared: 1.0, equation: "2.0*x + 0.0"}
```

### LaTeX formulas

```
eval_latex(r"\frac{a}{b}", {"a": 10, "b": 4})        → 2.5
eval_latex(r"\sqrt{a^{2} + b^{2}}", {"a": 3, "b": 4}) → 5.0
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MCP_CONSTRAINED_MODE` | `0` | Set to `1` to tighten dataset size limits (8 GB VRAM target) |

---

## Development

```bash
git clone https://github.com/azzindani/mcp_math.git
cd mcp_math
uv sync
uv run pytest                          # run test suite
uv run ruff check .                    # lint
MCP_CONSTRAINED_MODE=1 uv run pytest   # test constrained limits
uv run python verify_tool_docstrings.py  # check docstring lengths
```

---

## Architecture

```
server.py           ← MCP entry point — one-liner tool wrappers only
engine/
  __init__.py       ← thin router + re-exports
  sandbox.py        ← AST whitelist + cross-platform timeout
  deps.py           ← DAG builder + topological sort
  formatter.py      ← structured JSON output builder
_math_helpers.py    ← shared imports + _error() helper
_math_arithmetic.py ← calculate(), convert_units()
_math_algebra.py    ← solve(), simplify(), diff(), integrate()
_math_statistics.py ← describe(), regression()
_math_latex.py      ← eval_latex() 6-stage pipeline
shared/
  platform_utils.py ← is_constrained_mode(), get_max_*()
  progress.py       ← ok(), fail(), info(), warn()
```

No `eval()`. No `exec()`. No network calls. No state. Pure functions.

---

## License

MIT

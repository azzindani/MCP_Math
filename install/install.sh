#!/usr/bin/env bash
# install.sh — Install math-mcp-server to ~/.mcp_servers/math-mcp-server
set -euo pipefail

INSTALL_DIR="${HOME}/.mcp_servers/math-mcp-server"
REPO_URL="https://github.com/azzindani/mcp_math.git"

echo "=== math-mcp-server installer ==="

# Check dependencies
if ! command -v git &>/dev/null; then
    echo "ERROR: git is required. Install git and retry." >&2
    exit 1
fi

if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
fi

# Clone or update
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "Updating existing installation..."
    git -C "${INSTALL_DIR}" fetch origin
    git -C "${INSTALL_DIR}" reset --hard FETCH_HEAD
else
    echo "Cloning repository..."
    mkdir -p "$(dirname "${INSTALL_DIR}")"
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

cd "${INSTALL_DIR}"

# Install dependencies
echo "Installing Python dependencies..."
uv sync --no-dev

echo ""
echo "Installation complete: ${INSTALL_DIR}"
echo ""
echo "Add the following to your mcp.json:"
cat <<EOF
{
  "math-mcp-server": {
    "command": "bash",
    "args": ["-c", "cd ${INSTALL_DIR} && uv run python server.py --transport stdio"],
    "timeout": 600000
  }
}
EOF

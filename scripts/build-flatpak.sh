#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
SIDECARS="$FRONTEND/sidecars"
TARGET="${TARGET:-x86_64-unknown-linux-gnu}"

mkdir -p "$SIDECARS"

cd "$BACKEND"
python3 -m venv .venv-linux
".venv-linux/bin/python" -m pip install -r requirements-build.txt
".venv-linux/bin/python" -m PyInstaller entrypoint.py \
  --name cisco-backend \
  --onefile \
  --clean \
  --noconfirm \
  --distpath dist-linux \
  --workpath build-linux
cp "$BACKEND/dist-linux/cisco-backend" "$SIDECARS/cisco-backend-$TARGET"
chmod +x "$SIDECARS/cisco-backend-$TARGET"

cd "$FRONTEND"
npm install
npm run tauri build

cd "$ROOT"
flatpak-builder --force-clean --user --install-deps-from=flathub build-flatpak packaging/flatpak/local.cisco-client.app.yml
flatpak build-bundle ~/.local/share/flatpak/repo CiscoClient.flatpak local.cisco-client.app

echo "Flatpak bundle: $ROOT/CiscoClient.flatpak"

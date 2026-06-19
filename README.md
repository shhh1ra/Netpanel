# Cisco Client

Легкий SSH-клиент для Cisco 2960: Python backend выполняет show-команды через SSH, Vue + Tauri frontend дает компактный операторский интерфейс.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 17761
```

API будет доступен на `http://127.0.0.1:17761`.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Для Tauri:

```powershell
cd frontend
npm run tauri dev
```

## Релизные сборки

Схема такая: Python backend собирается через PyInstaller в sidecar-бинарь, Tauri кладет его рядом с приложением и запускает при старте UI. Поэтому пользователю не нужно отдельно запускать `uvicorn`.

Windows:

```powershell
.\scripts\build-windows.ps1
```

Артефакты появятся в `frontend/src-tauri/target/release` и `frontend/src-tauri/target/release/bundle`.

Flatpak собирается на Linux или в WSL с установленными `flatpak`, `flatpak-builder`, Rust, Node.js и Python:

```bash
./scripts/build-flatpak.sh
```

Итоговый bundle: `CiscoClient.flatpak`.

## Поддержанные действия

- `show running-config`
- `show ip arp`
- `show mac address-table address ...`
- `show mac address-table interface ...`
- `show ip bgp summary`, `show ip bgp`, `show ip bgp neighbors`
- `show ip ospf`, `show ip route ospf`, `show ip ospf neighbor`
- `show ip route static`
- `show ip route <address>` или `show ip route <network> <mask>`
- `show cdp neighbors [detail]`
- `show lldp neighbors [detail]`

# Netpanel

Netpanel - компактная SSH-панель для диагностики сетевого оборудования Cisco. Приложение запускает Python backend как Tauri sidecar, подключается к устройству по SSH и дает быстрый доступ к show-командам, таблицам, фильтрам и встроенному терминалу.

Текущая версия: `1.6.1`.

## Что умеет

- Подключение к Cisco по SSH с логином/паролем или SSH-ключом.
- Менеджер профилей хостов: имя, IP, порт, логин, тип авторизации, путь к ключу.
- Автопереподключение при выборе другого профиля.
- Возможность сохранить профиль без пароля и вводить пароль вручную перед подключением.
- Защищенное хранение сохраненных паролей на Windows через DPAPI.
- Встроенный SSH-терминал через WebSocket с базовыми терминальными клавишами.
- Быстрые команды для типовых задач диагностики.
- Человеческое представление результатов: таблицы, статусы, подсветка проблемных значений.
- Raw-режим для просмотра исходного вывода устройства.
- Сортировка и фильтры в таблицах, включая поиск по коротким алиасам интерфейсов вроде `fa` и `gi`.
- Копирование вывода одной кнопкой.
- Рестарт backend из интерфейса.
- Проверка новых версий через GitHub Releases при запуске и далее раз в 30 минут.

## Быстрые команды

Netpanel поддерживает следующие действия:

- Running config: `show running-config`.
- ARP-таблица: `show ip arp`.
- IP-интерфейсы: `show ip interface brief`.
- Статус интерфейсов:
  - `show interfaces status`;
  - `show interfaces summary`;
  - `show interfaces <interface>`.
- Детальная статистика интерфейса по ПКМ на строке таблицы интерфейсов.
- MAC/CAM-таблица:
  - `show mac address-table`;
  - `show mac address-table dynamic`;
  - поиск по MAC;
  - поиск по VLAN.
- Поиск устройства по IP:
  - `show ip arp | include <ip>`;
  - `show ip dhcp snooping binding | include <ip>`;
  - `show ip device tracking | include <ip>`;
  - дополнительный поиск MAC в CAM, если MAC найден через ARP/IPDT.
- BGP/OSPF:
  - таблицы маршрутизации;
  - summary;
  - соседи;
  - detail для OSPF neighbors.
- Статические маршруты: `show ip route static`.
- Проверка маршрута: `show ip route <address>` или `show ip route <network> <mask>`.
- CDP/LLDP-соседи:
  - `show cdp neighbors`;
  - `show cdp neighbors detail`;
  - `show lldp neighbors`;
  - `show lldp neighbors detail`.
- Ping и traceroute с устройства:
  - `ping <ip>`;
  - `ping <ip> source <interface>`;
  - `traceroute <ip>`.
- Система и мониторинг:
  - `show version`;
  - `show environment`;
  - `show env all`;
  - `show processes cpu history`;
  - `show memory statistics`.
- Логи: `show logging` с фильтром по ключевому слову и лимитом строк.

## Представление результатов

Для части команд Netpanel строит обзор вместо простого текстового вывода:

- таблицы интерфейсов с сортировкой и фильтрами;
- таблица IP-интерфейсов;
- таблица MAC-адресов;
- сводка поиска IP в ARP/DHCP Snooping/IP Device Tracking/CAM;
- ping/traceroute summary;
- системная карточка с версией IOS, hostname, uptime, платформой, serial и config register;
- статус железа и окружения с подсветкой `OK`, `Info`, проблемных и неподдерживаемых значений;
- детальная статистика интерфейса: MTU, bandwidth, duplex/speed, очереди, drops, CRC, input/output errors, collisions, resets, carrier и buffer counters.

В любой момент можно переключиться в `Raw`, чтобы увидеть оригинальный вывод Cisco IOS.

## Хранение профилей

Профили сохраняются в `hosts.json` рядом с portable-приложением. Это сделано специально для портативного режима: папку приложения можно переносить целиком.

На Windows сохраненные пароли защищаются через DPAPI и не пишутся в файл открытым текстом. DPAPI привязывает секрет к текущей учетной записи Windows, поэтому защищенный пароль не предназначен для переноса между пользователями или компьютерами.

Если профиль должен быть переносимым, сохранение пароля лучше отключить: Netpanel сохранит хост, порт, логин и тип авторизации, а пароль попросит вручную при подключении.

## SSH-ключи

В профиле можно выбрать режим авторизации `SSH-ключ` и указать путь к приватному ключу. Пароль при этом можно не сохранять. Если ключ защищен passphrase, дальнейшая поддержка passphrase может потребовать отдельного UI-сценария.

## Backend

В portable-сборке backend запускается автоматически как sidecar. Отдельно запускать `uvicorn` пользователю не нужно.

Для разработки backend можно поднять вручную:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 17761
```

API по умолчанию доступен на `http://127.0.0.1:17761`.

## Frontend

Разработка web-части:

```powershell
cd frontend
npm install
npm run dev
```

Запуск Tauri dev:

```powershell
cd frontend
npm run tauri dev
```

## Сборка Windows portable

Проект ориентирован на portable-сборки, инсталлеры не являются целевым форматом.

```powershell
.\scripts\build-windows.ps1
```

Скрипт делает следующее:

- собирает Python backend через PyInstaller в `netpanel-backend.exe`;
- копирует backend в Tauri sidecars;
- собирает frontend;
- собирает Tauri release;
- создает portable-папку с `Netpanel.exe` и `netpanel-backend.exe`;
- упаковывает ZIP.

Итоговый архив появляется здесь:

```text
frontend/src-tauri/target/release/Netpanel Portable <version>.zip
```

## Flatpak

Flatpak-сборка заготовлена для Linux/WSL-окружения с установленными `flatpak`, `flatpak-builder`, Rust, Node.js и Python:

```bash
./scripts/build-flatpak.sh
```

Итоговый bundle: `Netpanel.flatpak`.

## Релизы

Версия приложения хранится в:

- `frontend/package.json`;
- `frontend/src-tauri/tauri.conf.json`;
- `frontend/src-tauri/Cargo.toml`;
- `backend/main.py`.

Проверка обновлений смотрит последний релиз GitHub:

```text
https://github.com/shhh1ra/Netpanel/releases
```

Для публикации релиза используется тег вида `v1.6.1` и portable ZIP из `frontend/src-tauri/target/release`.

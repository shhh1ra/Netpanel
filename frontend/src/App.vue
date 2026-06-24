<script setup lang="ts">
import { writeText } from "@tauri-apps/api/clipboard";
import { Command, Child } from "@tauri-apps/api/shell";
import { invoke } from "@tauri-apps/api/tauri";
import { computed, nextTick, onMounted, reactive, ref } from "vue";

type Action =
  | "running_config"
  | "arp_table"
  | "mac_on_interface"
  | "routing_table"
  | "protocol_neighbors"
  | "static_routes"
  | "route_lookup"
  | "discovery_neighbors"
  | "interface_diagnostics"
  | "mac_table"
  | "ip_location";

type Protocol = "bgp" | "ospf";
type DiscoveryProtocol = "cdp" | "lldp" | "both";
type InterfaceView = "status" | "summary" | "detail";

interface HostProfile {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  password: string;
  authType: "password" | "key";
  keyPath?: string;
}

interface CommandOption {
  value: Action;
  label: string;
  description: string;
}

interface Presentation {
  kind: "interface_status" | "interface_summary" | "interface_detail" | "mac_table" | "ip_location";
  rows?: Record<string, any>[];
  metrics?: { label: string; value: string }[];
  sources?: { label: string; command: string; status: "found" | "empty" | "unsupported"; lines: string[] }[];
  interface?: string;
  state?: string;
  protocol?: string;
}

const apiBase = ref("http://127.0.0.1:17761");
const sessionId = ref("");
const connectedTo = ref("");
const isBusy = ref(false);
const error = ref("");
const output = ref("");
const presentation = ref<Presentation | null>(null);
const resultMode = ref<"human" | "raw">("human");
const terminalOutput = ref("");
const terminalInput = ref("");
const terminalPane = ref<HTMLElement | null>(null);
const issuedCommands = ref<string[]>([]);
const copied = ref(false);
const activeWorkspace = ref<"commands" | "terminal">("commands");
const backendChild = ref<Child | null>(null);
const hostProfiles = ref<HostProfile[]>([]);
const selectedHostId = ref("");
const hostProfileName = ref("");
const HOSTS_STORAGE_KEY = "netpanel-hosts";

const connection = reactive({
  host: "",
  port: 22,
  username: "",
  password: "",
});

const command = reactive({
  action: "running_config" as Action,
  protocol: "bgp" as Protocol,
  discovery_protocol: "both" as DiscoveryProtocol,
  mac_address: "",
  interface: "",
  route_query: "",
  interface_view: "status" as InterfaceView,
  vlan: null as number | null,
  dynamic_only: false,
  ip_address: "",
  detail: false,
});

const commandOptions: CommandOption[] = [
  { value: "running_config", label: "Скопировать running-config", description: "show running-config" },
  { value: "arp_table", label: "Скопировать ARP-таблицу", description: "show ip arp" },
  { value: "mac_on_interface", label: "Найти MAC на интерфейсе", description: "MAC lookup и проверка порта" },
  { value: "routing_table", label: "Таблица BGP / OSPF", description: "Маршруты и базовая сводка" },
  { value: "protocol_neighbors", label: "Соседи BGP / OSPF", description: "Соседства протоколов маршрутизации" },
  { value: "static_routes", label: "Статические маршруты", description: "show ip route static" },
  { value: "route_lookup", label: "Поиск адреса или диапазона", description: "Проверка существования маршрута" },
  { value: "discovery_neighbors", label: "Соседи CDP / LLDP", description: "Топология, имена, платформы и порты" },
  { value: "interface_diagnostics", label: "Статус интерфейсов", description: "Состояние, ошибки, загрузка и пропускная способность" },
  { value: "mac_table", label: "Таблица MAC-адресов", description: "CAM-таблица с поиском по MAC или VLAN" },
  { value: "ip_location", label: "Найти устройство по IP", description: "ARP, DHCP Snooping и IP Device Tracking" },
];

const selectedOption = computed(() => commandOptions.find((item) => item.value === command.action));
const isConnected = computed(() => Boolean(sessionId.value));
const needsProtocol = computed(() => ["routing_table", "protocol_neighbors"].includes(command.action));
const needsMac = computed(() => command.action === "mac_on_interface");
const needsRoute = computed(() => command.action === "route_lookup");
const needsDiscovery = computed(() => command.action === "discovery_neighbors");
const needsInterfaceDiagnostics = computed(() => command.action === "interface_diagnostics");
const needsMacTable = computed(() => command.action === "mac_table");
const needsIpLocation = computed(() => command.action === "ip_location");
const canRunAction = computed(() => {
  if (!isConnected.value || isBusy.value) return false;
  if (needsInterfaceDiagnostics.value && command.interface_view === "detail") return Boolean(command.interface.trim());
  if (needsIpLocation.value) return Boolean(command.ip_address.trim());
  return true;
});

onMounted(async () => {
  await loadHostProfiles();
  void startBundledBackend();
});

async function loadHostProfiles() {
  let legacyProfiles: Partial<HostProfile>[] = [];
  try {
    legacyProfiles = JSON.parse(localStorage.getItem(HOSTS_STORAGE_KEY) || "[]");
  } catch {
    localStorage.removeItem(HOSTS_STORAGE_KEY);
  }

  try {
    const storedProfiles = await invoke<HostProfile[] | null>("load_host_profiles");
    hostProfiles.value = (storedProfiles ?? legacyProfiles).map((profile) => ({
      id: profile.id || `${Date.now()}`,
      name: profile.name || profile.host || "Cisco",
      host: profile.host || "",
      port: profile.port || 22,
      username: profile.username || "",
      password: profile.password || "",
      authType: profile.authType || "password",
      keyPath: profile.keyPath,
    }));

    if (storedProfiles === null && hostProfiles.value.length) {
      await persistHostProfiles();
    }
    localStorage.removeItem(HOSTS_STORAGE_KEY);
  } catch {
    hostProfiles.value = legacyProfiles.map((profile) => ({
      id: profile.id || `${Date.now()}`,
      name: profile.name || profile.host || "Cisco",
      host: profile.host || "",
      port: profile.port || 22,
      username: profile.username || "",
      password: profile.password || "",
      authType: profile.authType || "password",
      keyPath: profile.keyPath,
    }));
  }
}

async function persistHostProfiles() {
  try {
    await invoke("save_host_profiles", { profiles: hostProfiles.value });
  } catch {
    localStorage.setItem(HOSTS_STORAGE_KEY, JSON.stringify(hostProfiles.value));
  }
}

function selectHostProfile() {
  const profile = hostProfiles.value.find((item) => item.id === selectedHostId.value);
  if (!profile) {
    hostProfileName.value = "";
    return;
  }

  hostProfileName.value = profile.name;
  connection.host = profile.host;
  connection.port = profile.port;
  connection.username = profile.username;
  connection.password = profile.password;
}

function saveHostProfile() {
  if (!connection.host.trim()) return;

  const existing = hostProfiles.value.find((item) => item.id === selectedHostId.value);
  const profile: HostProfile = {
    id: existing?.id || `${Date.now()}`,
    name: hostProfileName.value.trim() || connection.host.trim(),
    host: connection.host.trim(),
    port: connection.port,
    username: connection.username.trim(),
    password: connection.password,
    authType: existing?.authType || "password",
    keyPath: existing?.keyPath,
  };

  if (existing) {
    Object.assign(existing, profile);
  } else {
    hostProfiles.value.push(profile);
    selectedHostId.value = profile.id;
  }

  hostProfileName.value = profile.name;
  void persistHostProfiles();
}

function deleteHostProfile() {
  if (!selectedHostId.value) return;
  hostProfiles.value = hostProfiles.value.filter((item) => item.id !== selectedHostId.value);
  selectedHostId.value = "";
  hostProfileName.value = "";
  void persistHostProfiles();
}

async function startBundledBackend() {

  try {
    const backend = Command.sidecar("../sidecars/netpanel-backend", [], {
      env: {
        CISCO_CLIENT_HOST: "127.0.0.1",
        CISCO_CLIENT_PORT: "17761",
      },
    });
    backendChild.value = await backend.spawn();
  } catch (err) {
    console.warn("Bundled backend was not started", err);
  }
}

async function connect() {
  error.value = "";
  output.value = "";
  presentation.value = null;
  terminalOutput.value = "";
  terminalInput.value = "";
  issuedCommands.value = [];
  isBusy.value = true;

  try {
    const response = await fetch(`${apiBase.value}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(connection),
    });
    const data = await parseResponse(response);
    sessionId.value = data.session_id;
    connectedTo.value = `${data.username}@${data.host}`;
    terminalOutput.value = `Подключено к ${data.username}@${data.host}`;
    await scrollTerminalToEnd();
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    isBusy.value = false;
  }
}

async function disconnect() {
  if (!sessionId.value) return;
  isBusy.value = true;
  error.value = "";

  try {
    await fetch(`${apiBase.value}/sessions/${sessionId.value}`, { method: "DELETE" });
  } finally {
    sessionId.value = "";
    connectedTo.value = "";
    terminalInput.value = "";
    isBusy.value = false;
  }
}

async function runCommand() {
  if (!sessionId.value) return;
  error.value = "";
  output.value = "";
  presentation.value = null;
  issuedCommands.value = [];
  activeWorkspace.value = "commands";
  isBusy.value = true;

  const payload = {
    action: command.action,
    protocol: needsProtocol.value ? command.protocol : null,
    discovery_protocol: command.discovery_protocol,
    mac_address: command.mac_address || null,
    interface: command.interface || null,
    route_query: command.route_query || null,
    interface_view: command.interface_view,
    vlan: command.vlan || null,
    dynamic_only: command.dynamic_only,
    ip_address: command.ip_address || null,
    detail: command.detail,
  };

  try {
    const response = await fetch(`${apiBase.value}/sessions/${sessionId.value}/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await parseResponse(response);
    issuedCommands.value = data.commands;
    output.value = data.output || "Команда выполнена без текстового вывода.";
    presentation.value = data.presentation || null;
    resultMode.value = presentation.value ? "human" : "raw";
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    isBusy.value = false;
  }
}

async function runTerminalCommand() {
  if (!sessionId.value || !terminalInput.value.trim()) return;

  const rawCommand = terminalInput.value.trim();
  terminalInput.value = "";
  error.value = "";
  isBusy.value = true;
  activeWorkspace.value = "terminal";
  terminalOutput.value += `${terminalOutput.value ? "\n\n" : ""}$ ${rawCommand}\n`;
  await scrollTerminalToEnd();

  try {
    const response = await fetch(`${apiBase.value}/sessions/${sessionId.value}/terminal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: rawCommand }),
    });
    const data = await parseResponse(response);
    terminalOutput.value += data.output || "Команда выполнена без текстового вывода.";
  } catch (err) {
    const message = errorMessage(err);
    error.value = message;
    terminalOutput.value += `Ошибка: ${message}`;
  } finally {
    await scrollTerminalToEnd();
    isBusy.value = false;
  }
}

async function scrollTerminalToEnd() {
  await nextTick();
  if (terminalPane.value) {
    terminalPane.value.scrollTop = terminalPane.value.scrollHeight;
  }
}

async function copyOutput() {
  const text = activeWorkspace.value === "terminal" ? terminalOutput.value : output.value;
  if (!text) return;

  await writeText(text);

  copied.value = true;
  window.setTimeout(() => {
    copied.value = false;
  }, 1400);
}

async function parseResponse(response: Response) {
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }
  return data;
}

function errorMessage(err: unknown) {
  return err instanceof Error ? err.message : "Неизвестная ошибка";
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    connected: "Подключён",
    notconnect: "Нет подключения",
    disabled: "Отключён",
    "err-disabled": "Ошибка",
    inactive: "Неактивен",
  };
  return labels[value.toLowerCase()] || value;
}

function formatRate(bitsPerSecond: number) {
  if (!bitsPerSecond) return "0 бит/с";
  if (bitsPerSecond >= 1_000_000_000) return `${(bitsPerSecond / 1_000_000_000).toFixed(1)} Гбит/с`;
  if (bitsPerSecond >= 1_000_000) return `${(bitsPerSecond / 1_000_000).toFixed(1)} Мбит/с`;
  if (bitsPerSecond >= 1_000) return `${(bitsPerSecond / 1_000).toFixed(1)} Кбит/с`;
  return `${bitsPerSecond} бит/с`;
}

function speedLabel(value: string) {
  const normalized = value.toLowerCase();
  const automatic = normalized.startsWith("a-");
  const speed = normalized.replace(/^a-/, "");
  if (speed === "auto") return "Auto";
  if (/^\d+$/.test(speed)) {
    const numeric = Number(speed);
    const label = numeric >= 1000 ? `${numeric / 1000} Гбит/с` : `${numeric} Мбит/с`;
    return automatic ? `${label} (auto)` : label;
  }
  return value || "—";
}

function duplexLabel(value: string) {
  const labels: Record<string, string> = {
    full: "Full",
    half: "Half",
    "a-full": "Full (auto)",
    "a-half": "Half (auto)",
    auto: "Auto",
  };
  return labels[value.toLowerCase()] || value || "—";
}

function metricValue(metric: { label: string; value: string }) {
  const value = Number(metric.value);
  if (metric.label === "Пропускная способность") return formatRate(value * 1000);
  if (metric.label.includes("трафик")) return formatRate(value);
  if (metric.label.includes("пакеты")) return `${value} пак/с`;
  if (metric.label === "MTU") return `${value} байт`;
  if (metric.label === "Задержка") return `${value} мкс`;
  if (metric.label === "Надёжность" || metric.label.includes("Загрузка")) {
    const [current, maximum] = metric.value.split("/").map(Number);
    if (maximum) return `${Math.round((current / maximum) * 100)}%`;
  }
  return metric.value;
}
</script>

<template>
  <main class="shell">
    <section class="side">
      <div class="brand">
        <div class="mark">2960</div>
        <div>
          <h1>Netpanel</h1>
          <p>SSH-панель для быстрых show-команд</p>
        </div>
      </div>

      <form class="panel" @submit.prevent="connect">
        <div class="panel-head">
          <h2>Подключение</h2>
          <span class="status" :class="{ online: isConnected }">{{ isConnected ? "online" : "offline" }}</span>
        </div>

        <div class="host-manager">
          <label>
            Профиль
            <select v-model="selectedHostId" @change="selectHostProfile">
              <option value="">Новый хост</option>
              <option v-for="profile in hostProfiles" :key="profile.id" :value="profile.id">
                {{ profile.name }} — {{ profile.host }}
              </option>
            </select>
          </label>
          <label>
            Название
            <input v-model="hostProfileName" placeholder="Например, SW1" autocomplete="off" />
          </label>
          <div class="host-actions">
            <button type="button" :disabled="!connection.host" @click="saveHostProfile">Сохранить</button>
            <button type="button" :disabled="!selectedHostId" @click="deleteHostProfile">Удалить</button>
          </div>
        </div>

        <label>
          API backend
          <input v-model="apiBase" autocomplete="off" />
        </label>
        <label>
          Хост
          <input v-model="connection.host" placeholder="192.168.1.10" autocomplete="off" required />
        </label>
        <div class="grid two">
          <label>
            Порт
            <input v-model.number="connection.port" type="number" min="1" max="65535" required />
          </label>
          <label>
            Логин
            <input v-model="connection.username" autocomplete="username" required />
          </label>
        </div>
        <label>
          Пароль
          <input v-model="connection.password" type="password" autocomplete="current-password" required />
        </label>

        <div class="actions">
          <button class="primary" type="submit" :disabled="isBusy || isConnected">Подключиться</button>
          <button type="button" :disabled="isBusy || !isConnected" @click="disconnect">Отключиться</button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-head">
          <h2>Действие</h2>
          <span>{{ selectedOption?.description }}</span>
        </div>

        <label>
          Команда
          <select v-model="command.action">
            <option v-for="option in commandOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <div v-if="needsProtocol" class="segmented">
          <button type="button" :class="{ active: command.protocol === 'bgp' }" @click="command.protocol = 'bgp'">
            BGP
          </button>
          <button type="button" :class="{ active: command.protocol === 'ospf' }" @click="command.protocol = 'ospf'">
            OSPF
          </button>
        </div>

        <div v-if="needsDiscovery" class="segmented">
          <button type="button" :class="{ active: command.discovery_protocol === 'both' }" @click="command.discovery_protocol = 'both'">
            CDP + LLDP
          </button>
          <button type="button" :class="{ active: command.discovery_protocol === 'cdp' }" @click="command.discovery_protocol = 'cdp'">
            CDP
          </button>
          <button type="button" :class="{ active: command.discovery_protocol === 'lldp' }" @click="command.discovery_protocol = 'lldp'">
            LLDP
          </button>
        </div>

        <div v-if="needsInterfaceDiagnostics" class="segmented">
          <button type="button" :class="{ active: command.interface_view === 'status' }" @click="command.interface_view = 'status'">
            Статус
          </button>
          <button type="button" :class="{ active: command.interface_view === 'summary' }" @click="command.interface_view = 'summary'">
            Сводка
          </button>
          <button type="button" :class="{ active: command.interface_view === 'detail' }" @click="command.interface_view = 'detail'">
            Интерфейс
          </button>
        </div>

        <label v-if="needsInterfaceDiagnostics && command.interface_view === 'detail'">
          Интерфейс
          <input v-model="command.interface" placeholder="FastEthernet0/1" autocomplete="off" />
        </label>

        <label v-if="needsMac">
          MAC-адрес
          <input v-model="command.mac_address" placeholder="0011.2233.4455" autocomplete="off" />
        </label>
        <label v-if="needsMac">
          Интерфейс, если нужно уточнить
          <input v-model="command.interface" placeholder="FastEthernet0/1" autocomplete="off" />
        </label>

        <div v-if="needsMacTable" class="grid two">
          <label>
            MAC-адрес
            <input v-model="command.mac_address" placeholder="0011.2233.4455" autocomplete="off" />
          </label>
          <label>
            VLAN
            <input v-model.number="command.vlan" type="number" min="1" max="4094" placeholder="10" />
          </label>
        </div>
        <label v-if="needsMacTable" class="check">
          <input v-model="command.dynamic_only" type="checkbox" />
          Только динамические записи
        </label>

        <label v-if="needsRoute">
          Адрес или CIDR
          <input v-model="command.route_query" placeholder="10.10.10.0/24" autocomplete="off" />
        </label>
        <label v-if="needsIpLocation">
          IP-адрес
          <input v-model="command.ip_address" placeholder="10.10.10.25" autocomplete="off" />
        </label>

        <label v-if="needsDiscovery || command.action === 'protocol_neighbors'" class="check">
          <input v-model="command.detail" type="checkbox" />
          Подробный вывод
        </label>

        <button class="run" type="button" :disabled="!canRunAction" @click="runCommand">
          {{ isBusy ? "Выполняю..." : "Выполнить" }}
        </button>
      </section>
    </section>

    <section class="workspace">
      <header class="topbar">
        <div>
          <span class="eyebrow">Сессия</span>
          <strong>{{ connectedTo || "нет подключения" }}</strong>
        </div>
        <div class="workspace-tabs">
          <button type="button" :class="{ active: activeWorkspace === 'commands' }" @click="activeWorkspace = 'commands'">
            Команды
          </button>
          <button type="button" :class="{ active: activeWorkspace === 'terminal' }" @click="activeWorkspace = 'terminal'">
            Терминал
          </button>
        </div>
        <div class="command-list" v-if="activeWorkspace === 'commands' && issuedCommands.length">
          <code v-for="item in issuedCommands" :key="item">{{ item }}</code>
        </div>
      </header>

      <div v-if="error" class="notice error">{{ error }}</div>

      <div v-if="activeWorkspace === 'commands'" class="terminal-wrap command-result">
        <button
          v-if="output"
          class="copy-output"
          type="button"
          :title="copied ? 'Скопировано' : 'Копировать вывод'"
          :aria-label="copied ? 'Скопировано' : 'Копировать вывод'"
          @click="copyOutput"
        >
          {{ copied ? "✓" : "⧉" }}
        </button>

        <div v-if="presentation" class="result-toolbar">
          <div class="result-tabs">
            <button type="button" :class="{ active: resultMode === 'human' }" @click="resultMode = 'human'">Обзор</button>
            <button type="button" :class="{ active: resultMode === 'raw' }" @click="resultMode = 'raw'">Raw</button>
          </div>
        </div>

        <div v-if="presentation && resultMode === 'human'" class="human-output">
          <div v-if="presentation.kind === 'interface_status'" class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Состояние</th>
                  <th>Интерфейс</th>
                  <th>Имя</th>
                  <th>VLAN</th>
                  <th>Duplex</th>
                  <th>Скорость</th>
                  <th>Тип</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in presentation.rows" :key="row.port">
                  <td><span class="state-dot" :class="{ up: row.up }"></span>{{ statusLabel(row.status) }}</td>
                  <td class="mono">{{ row.port }}</td>
                  <td>{{ row.name || "—" }}</td>
                  <td>{{ row.vlan || "—" }}</td>
                  <td>{{ duplexLabel(row.duplex) }}</td>
                  <td>{{ speedLabel(row.speed) }}</td>
                  <td>{{ row.type || "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else-if="presentation.kind === 'interface_summary'" class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Состояние</th>
                  <th>Интерфейс</th>
                  <th>Приём</th>
                  <th>Передача</th>
                  <th>RX пак/с</th>
                  <th>TX пак/с</th>
                  <th>Потери</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in presentation.rows" :key="row.interface">
                  <td><span class="state-dot" :class="{ up: row.up }"></span>{{ row.up ? "UP" : "DOWN" }}</td>
                  <td class="mono">{{ row.interface }}</td>
                  <td>{{ formatRate(row.rx_bps) }}</td>
                  <td>{{ formatRate(row.tx_bps) }}</td>
                  <td>{{ row.rx_pps }}</td>
                  <td>{{ row.tx_pps }}</td>
                  <td :class="{ warning: row.input_drops + row.output_drops > 0 }">
                    {{ row.input_drops + row.output_drops }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else-if="presentation.kind === 'interface_detail'" class="detail-output">
            <div class="detail-heading">
              <div>
                <span class="eyebrow">Интерфейс</span>
                <strong class="mono">{{ presentation.interface || "—" }}</strong>
              </div>
              <div class="detail-states">
                <span :class="{ good: presentation.state === 'up' }">Порт: {{ presentation.state || "неизвестно" }}</span>
                <span :class="{ good: presentation.protocol === 'up' }">Протокол: {{ presentation.protocol || "неизвестно" }}</span>
              </div>
            </div>
            <dl class="metric-grid">
              <div v-for="metric in presentation.metrics" :key="metric.label">
                <dt>{{ metric.label }}</dt>
                <dd>{{ metricValue(metric) }}</dd>
              </div>
            </dl>
          </div>

          <div v-else-if="presentation.kind === 'mac_table'" class="table-scroll">
            <table>
              <thead>
                <tr><th>VLAN</th><th>MAC-адрес</th><th>Тип</th><th>Порт</th></tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in presentation.rows" :key="`${row.mac}-${row.vlan}-${index}`">
                  <td>{{ row.vlan }}</td>
                  <td class="mono">{{ row.mac }}</td>
                  <td>{{ row.entry_type === "DYNAMIC" ? "Динамический" : row.entry_type }}</td>
                  <td class="mono">{{ row.port }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else-if="presentation.kind === 'ip_location'" class="source-list">
            <section v-for="source in presentation.sources" :key="source.label" class="source-section">
              <header>
                <div>
                  <strong>{{ source.label }}</strong>
                  <code>{{ source.command }}</code>
                </div>
                <span class="source-status" :class="source.status">
                  {{ source.status === "found" ? "Найдено" : source.status === "unsupported" ? "Не поддерживается" : "Нет данных" }}
                </span>
              </header>
              <pre v-if="source.lines.length">{{ source.lines.join("\n") }}</pre>
            </section>
          </div>
        </div>

        <pre v-else class="terminal" :class="{ empty: !output }">{{ output || "После подключения выбери действие слева. Результат появится здесь." }}</pre>
      </div>

      <div v-else class="terminal-wrap interactive-terminal">
        <button
          v-if="terminalOutput"
          class="copy-output"
          type="button"
          :title="copied ? 'Скопировано' : 'Копировать терминал'"
          :aria-label="copied ? 'Скопировано' : 'Копировать терминал'"
          @click="copyOutput"
        >
          {{ copied ? "✓" : "⧉" }}
        </button>
        <pre ref="terminalPane" class="terminal" :class="{ empty: !terminalOutput }">{{ terminalOutput || "Подключись к устройству и отправляй команды прямо отсюда." }}</pre>
        <form class="terminal-input" @submit.prevent="runTerminalCommand">
          <span>$</span>
          <input
            v-model="terminalInput"
            :disabled="isBusy || !isConnected"
            autocomplete="off"
            placeholder="show interfaces status"
          />
          <button type="submit" :disabled="isBusy || !isConnected || !terminalInput.trim()">Ввод</button>
        </form>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { writeText } from "@tauri-apps/api/clipboard";
import { Command, Child } from "@tauri-apps/api/shell";
import { computed, onMounted, reactive, ref } from "vue";

type Action =
  | "running_config"
  | "arp_table"
  | "mac_on_interface"
  | "routing_table"
  | "protocol_neighbors"
  | "static_routes"
  | "route_lookup"
  | "discovery_neighbors";

type Protocol = "bgp" | "ospf";
type DiscoveryProtocol = "cdp" | "lldp" | "both";

interface HostProfile {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
}

interface CommandOption {
  value: Action;
  label: string;
  description: string;
}

const apiBase = ref("http://127.0.0.1:17761");
const sessionId = ref("");
const connectedTo = ref("");
const isBusy = ref(false);
const error = ref("");
const output = ref("");
const issuedCommands = ref<string[]>([]);
const copied = ref(false);
const backendChild = ref<Child | null>(null);
const hostProfiles = ref<HostProfile[]>([]);
const selectedHostId = ref("");
const hostProfileName = ref("");
const HOSTS_STORAGE_KEY = "cisco-client-hosts";

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
];

const selectedOption = computed(() => commandOptions.find((item) => item.value === command.action));
const isConnected = computed(() => Boolean(sessionId.value));
const needsProtocol = computed(() => ["routing_table", "protocol_neighbors"].includes(command.action));
const needsMac = computed(() => command.action === "mac_on_interface");
const needsRoute = computed(() => command.action === "route_lookup");
const needsDiscovery = computed(() => command.action === "discovery_neighbors");

onMounted(() => {
  loadHostProfiles();
  void startBundledBackend();
});

function loadHostProfiles() {
  try {
    hostProfiles.value = JSON.parse(localStorage.getItem(HOSTS_STORAGE_KEY) || "[]");
  } catch {
    hostProfiles.value = [];
  }
}

function persistHostProfiles() {
  localStorage.setItem(HOSTS_STORAGE_KEY, JSON.stringify(hostProfiles.value));
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
  connection.password = "";
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
  };

  if (existing) {
    Object.assign(existing, profile);
  } else {
    hostProfiles.value.push(profile);
    selectedHostId.value = profile.id;
  }

  hostProfileName.value = profile.name;
  persistHostProfiles();
}

function deleteHostProfile() {
  if (!selectedHostId.value) return;
  hostProfiles.value = hostProfiles.value.filter((item) => item.id !== selectedHostId.value);
  selectedHostId.value = "";
  hostProfileName.value = "";
  persistHostProfiles();
}

async function startBundledBackend() {

  try {
    const backend = Command.sidecar("../sidecars/cisco-backend", [], {
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
    isBusy.value = false;
  }
}

async function runCommand() {
  if (!sessionId.value) return;
  error.value = "";
  output.value = "";
  issuedCommands.value = [];
  isBusy.value = true;

  const payload = {
    action: command.action,
    protocol: needsProtocol.value ? command.protocol : null,
    discovery_protocol: command.discovery_protocol,
    mac_address: command.mac_address || null,
    interface: command.interface || null,
    route_query: command.route_query || null,
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
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    isBusy.value = false;
  }
}

async function copyOutput() {
  if (!output.value) return;

  await writeText(output.value);

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
</script>

<template>
  <main class="shell">
    <section class="side">
      <div class="brand">
        <div class="mark">2960</div>
        <div>
          <h1>Cisco Client</h1>
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

        <label v-if="needsMac">
          MAC-адрес
          <input v-model="command.mac_address" placeholder="0011.2233.4455" autocomplete="off" />
        </label>
        <label v-if="needsMac">
          Интерфейс, если нужно уточнить
          <input v-model="command.interface" placeholder="FastEthernet0/1" autocomplete="off" />
        </label>
        <label v-if="needsRoute">
          Адрес или CIDR
          <input v-model="command.route_query" placeholder="10.10.10.0/24" autocomplete="off" />
        </label>

        <label v-if="needsDiscovery || command.action === 'protocol_neighbors'" class="check">
          <input v-model="command.detail" type="checkbox" />
          Подробный вывод
        </label>

        <button class="run" type="button" :disabled="isBusy || !isConnected" @click="runCommand">
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
        <div class="command-list" v-if="issuedCommands.length">
          <code v-for="item in issuedCommands" :key="item">{{ item }}</code>
        </div>
      </header>

      <div v-if="error" class="notice error">{{ error }}</div>

      <div class="terminal-wrap">
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
        <pre class="terminal" :class="{ empty: !output }">{{ output || "После подключения выбери действие слева. Результат появится здесь." }}</pre>
      </div>
    </section>
  </main>
</template>

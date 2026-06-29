<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { Presentation, ResultMode } from "../../types/netpanel";
import {
  duplexLabel, formatRate, ipInterfaceStatusLabel, ipMethodLabel,
  metricValue, speedLabel, statusLabel,
} from "../../utils/resultFormatters";

type SortDirection = "asc" | "desc";
type SortValue = string | number | boolean | null | undefined;
type SortColumn = { key: string; label: string; get: (row: Record<string, any>) => SortValue };

const props = defineProps<{ output: string; presentation: Presentation | null; copied: boolean }>();
const emit = defineEmits<{ copy: [] }>();
const mode = defineModel<ResultMode>("mode", { required: true });

const sortKey = ref("");
const sortDirection = ref<SortDirection>("asc");

const collator = new Intl.Collator("ru", { numeric: true, sensitivity: "base" });

const columns = computed<SortColumn[]>(() => {
  if (!props.presentation) return [];
  if (props.presentation.kind === "interface_status") {
    return [
      { key: "status", label: "Состояние", get: (row) => row.status },
      { key: "port", label: "Интерфейс", get: (row) => row.port },
      { key: "name", label: "Имя", get: (row) => row.name },
      { key: "vlan", label: "VLAN", get: (row) => row.vlan },
      { key: "duplex", label: "Duplex", get: (row) => row.duplex },
      { key: "speed", label: "Скорость", get: (row) => speedSortValue(row.speed) },
      { key: "type", label: "Тип", get: (row) => row.type },
    ];
  }
  if (props.presentation.kind === "interface_summary") {
    return [
      { key: "up", label: "Состояние", get: (row) => row.up },
      { key: "interface", label: "Интерфейс", get: (row) => row.interface },
      { key: "rx_bps", label: "Приём", get: (row) => row.rx_bps },
      { key: "tx_bps", label: "Передача", get: (row) => row.tx_bps },
      { key: "rx_pps", label: "RX пак/с", get: (row) => row.rx_pps },
      { key: "tx_pps", label: "TX пак/с", get: (row) => row.tx_pps },
      { key: "drops", label: "Потери", get: (row) => row.input_drops + row.output_drops },
    ];
  }
  if (props.presentation.kind === "ip_interface_brief") {
    return [
      { key: "up", label: "Состояние", get: (row) => row.up },
      { key: "interface", label: "Интерфейс", get: (row) => row.interface },
      { key: "ip_address", label: "IP-адрес", get: (row) => row.ip_address },
      { key: "method", label: "Источник", get: (row) => row.method },
      { key: "status", label: "Порт", get: (row) => row.status },
      { key: "protocol", label: "Протокол", get: (row) => row.protocol },
    ];
  }
  if (props.presentation.kind === "mac_table") {
    return [
      { key: "vlan", label: "VLAN", get: (row) => vlanSortValue(row.vlan) },
      { key: "mac", label: "MAC-адрес", get: (row) => row.mac },
      { key: "entry_type", label: "Тип", get: (row) => row.entry_type },
      { key: "port", label: "Порт", get: (row) => row.port },
    ];
  }
  if (props.presentation.kind === "ip_location") {
    return [
      { key: "source", label: "Источник", get: (row) => row.source },
      { key: "ip_address", label: "IP-адрес", get: (row) => row.ip_address },
      { key: "mac", label: "MAC-адрес", get: (row) => row.mac },
      { key: "vlan", label: "VLAN", get: (row) => vlanSortValue(row.vlan) },
      { key: "port", label: "Порт", get: (row) => row.port },
      { key: "entry_type", label: "Тип", get: (row) => row.entry_type },
    ];
  }
  if (props.presentation.kind === "reachability") {
    return [
      { key: "hop", label: "Hop", get: (row) => Number(row.hop) },
      { key: "result", label: "Ответ", get: (row) => row.result },
    ];
  }
  if (props.presentation.kind === "system_monitoring") {
    return [
      { key: "item", label: "Узел", get: (row) => row.item },
      { key: "status", label: "Статус", get: (row) => row.status },
      { key: "detail", label: "Детали", get: (row) => row.detail },
    ];
  }
  if (props.presentation.kind === "logs") {
    return [
      { key: "severity", label: "Severity", get: (row) => Number(row.severity || 99) },
      { key: "facility", label: "Facility", get: (row) => row.facility },
      { key: "mnemonic", label: "Событие", get: (row) => row.mnemonic },
      { key: "message", label: "Сообщение", get: (row) => row.message },
    ];
  }
  return [];
});

const sortedRows = computed(() => {
  const rows = props.presentation?.kind === "system_monitoring"
    ? [...(props.presentation.environment ?? [])]
    : [...(props.presentation?.rows ?? [])];
  const column = columns.value.find((item) => item.key === sortKey.value);
  if (!column) return rows;

  return rows.sort((left, right) => {
    const result = compareValues(column.get(left), column.get(right));
    return sortDirection.value === "asc" ? result : -result;
  });
});

watch(() => props.presentation?.kind, () => {
  sortKey.value = "";
  sortDirection.value = "asc";
});

function sortBy(key: string) {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  sortKey.value = key;
  sortDirection.value = "asc";
}

function sortLabel(key: string) {
  if (sortKey.value !== key) return "";
  return sortDirection.value === "asc" ? "↑" : "↓";
}

function compareValues(left: SortValue, right: SortValue) {
  const leftEmpty = left === null || left === undefined || left === "";
  const rightEmpty = right === null || right === undefined || right === "";
  if (leftEmpty && rightEmpty) return 0;
  if (leftEmpty) return 1;
  if (rightEmpty) return -1;
  if (typeof left === "number" && typeof right === "number") return left - right;
  if (typeof left === "boolean" && typeof right === "boolean") return Number(right) - Number(left);
  return collator.compare(String(left), String(right));
}

function speedSortValue(value: string) {
  const numeric = Number(String(value || "").trim().toLowerCase().replace(/^a-/, "").replace(/^-/, ""));
  return Number.isFinite(numeric) ? numeric : value;
}

function vlanSortValue(value: string) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : value;
}
</script>

<template>
  <div class="terminal-wrap command-result">
    <button
      v-if="output"
      class="copy-output"
      type="button"
      :title="copied ? 'Скопировано' : 'Копировать вывод'"
      :aria-label="copied ? 'Скопировано' : 'Копировать вывод'"
      @click="emit('copy')"
    >{{ copied ? "✓" : "⧉" }}</button>

    <div v-if="presentation" class="result-toolbar">
      <div class="result-tabs">
        <button type="button" :class="{ active: mode === 'human' }" @click="mode = 'human'">Обзор</button>
        <button type="button" :class="{ active: mode === 'raw' }" @click="mode = 'raw'">Raw</button>
      </div>
    </div>

    <div v-if="presentation && mode === 'human'" class="human-output">
      <div v-if="presentation.kind === 'interface_status'" class="table-scroll">
        <table>
          <thead><tr>
            <th v-for="column in columns" :key="column.key">
              <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
            </th>
          </tr></thead>
          <tbody>
            <tr v-for="row in sortedRows" :key="row.port">
              <td><span class="state-dot" :class="{ up: row.up }"></span>{{ statusLabel(row.status) }}</td>
              <td class="mono">{{ row.port }}</td><td>{{ row.name || "—" }}</td><td>{{ row.vlan || "—" }}</td>
              <td>{{ duplexLabel(row.duplex) }}</td><td>{{ speedLabel(row.speed) }}</td><td>{{ row.type || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="presentation.kind === 'interface_summary'" class="table-scroll">
        <table>
          <thead><tr>
            <th v-for="column in columns" :key="column.key">
              <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
            </th>
          </tr></thead>
          <tbody>
            <tr v-for="row in sortedRows" :key="row.interface">
              <td><span class="state-dot" :class="{ up: row.up }"></span>{{ row.up ? "UP" : "DOWN" }}</td>
              <td class="mono">{{ row.interface }}</td><td>{{ formatRate(row.rx_bps) }}</td><td>{{ formatRate(row.tx_bps) }}</td>
              <td>{{ row.rx_pps }}</td><td>{{ row.tx_pps }}</td>
              <td :class="{ warning: row.input_drops + row.output_drops > 0 }">{{ row.input_drops + row.output_drops }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="presentation.kind === 'interface_detail'" class="detail-output">
        <div class="detail-heading">
          <div><span class="eyebrow">Интерфейс</span><strong class="mono">{{ presentation.interface || "—" }}</strong></div>
          <div class="detail-states">
            <span :class="{ good: presentation.state === 'up' }">Порт: {{ presentation.state || "неизвестно" }}</span>
            <span :class="{ good: presentation.protocol === 'up' }">Протокол: {{ presentation.protocol || "неизвестно" }}</span>
          </div>
        </div>
        <dl class="metric-grid">
          <div v-for="metric in presentation.metrics" :key="metric.label"><dt>{{ metric.label }}</dt><dd>{{ metricValue(metric) }}</dd></div>
        </dl>
      </div>

      <div v-else-if="presentation.kind === 'ip_interface_brief'" class="table-scroll">
        <table>
          <thead><tr>
            <th v-for="column in columns" :key="column.key">
              <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
            </th>
          </tr></thead>
          <tbody>
            <tr v-for="row in sortedRows" :key="row.interface">
              <td><span class="state-dot" :class="{ up: row.up }"></span>{{ row.up ? "UP" : "DOWN" }}</td>
              <td class="mono">{{ row.interface }}</td>
              <td class="mono">{{ row.ip_address === "unassigned" ? "Не назначен" : row.ip_address }}</td>
              <td>{{ ipMethodLabel(row.method) }}</td><td>{{ ipInterfaceStatusLabel(row.status) }}</td>
              <td>{{ row.protocol.toLowerCase() === "up" ? "UP" : "DOWN" }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="presentation.kind === 'mac_table'" class="table-scroll">
        <table>
          <thead><tr>
            <th v-for="column in columns" :key="column.key">
              <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
            </th>
          </tr></thead>
          <tbody>
            <tr v-for="(row, index) in sortedRows" :key="`${row.mac}-${row.vlan}-${index}`">
              <td>{{ row.vlan }}</td><td class="mono">{{ row.mac }}</td>
              <td>{{ row.entry_type === "DYNAMIC" ? "Динамический" : row.entry_type }}</td><td class="mono">{{ row.port }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="presentation.kind === 'ip_location'" class="source-list">
        <div v-if="sortedRows.length" class="table-scroll location-table">
          <table>
            <thead><tr>
              <th v-for="column in columns" :key="column.key">
                <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
              </th>
            </tr></thead>
            <tbody>
              <tr v-for="(row, index) in sortedRows" :key="`${row.source}-${row.mac}-${row.port}-${index}`">
                <td>{{ row.source }}</td>
                <td class="mono">{{ row.ip_address || "—" }}</td>
                <td class="mono">{{ row.mac || "—" }}</td>
                <td>{{ row.vlan || "—" }}</td>
                <td class="mono">{{ row.port || "—" }}</td>
                <td>{{ row.entry_type || "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <section v-for="source in presentation.sources" :key="source.label" class="source-section">
          <header>
            <div><strong>{{ source.label }}</strong><code>{{ source.command }}</code></div>
            <span class="source-status" :class="source.status">
              {{ source.status === "found" ? "Найдено" : source.status === "unsupported" ? "Не поддерживается" : "Нет данных" }}
            </span>
          </header>
          <pre v-if="source.lines.length">{{ source.lines.join("\n") }}</pre>
        </section>
      </div>

      <div v-else-if="presentation.kind === 'reachability'" class="detail-output">
        <div class="detail-heading">
          <div>
            <span class="eyebrow">{{ presentation.mode === "traceroute" ? "Traceroute" : "Ping" }}</span>
            <strong class="mono">{{ presentation.command || "—" }}</strong>
          </div>
          <div class="detail-states">
            <span :class="{ good: presentation.status === 'ok' || presentation.status === 'complete' }">
              {{ presentation.status === "ok" ? "Есть ответ" : presentation.status === "failed" ? "Нет ответа" : "Выполнено" }}
            </span>
          </div>
        </div>
        <dl v-if="presentation.metrics?.length" class="metric-grid">
          <div v-for="metric in presentation.metrics" :key="metric.label"><dt>{{ metric.label }}</dt><dd>{{ metric.value }}</dd></div>
        </dl>
        <div v-if="sortedRows.length" class="table-scroll reachability-table">
          <table>
            <thead><tr>
              <th v-for="column in columns" :key="column.key">
                <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
              </th>
            </tr></thead>
            <tbody>
              <tr v-for="row in sortedRows" :key="row.hop">
                <td>{{ row.hop }}</td>
                <td class="mono">{{ row.result }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else-if="presentation.kind === 'system_monitoring'" class="detail-output">
        <div class="detail-heading">
          <div>
            <span class="eyebrow">Система</span>
            <strong>Версия, uptime, CPU, память и питание</strong>
          </div>
        </div>
        <dl v-if="presentation.metrics?.length" class="metric-grid">
          <div v-for="metric in presentation.metrics" :key="metric.label"><dt>{{ metric.label }}</dt><dd>{{ metric.value }}</dd></div>
        </dl>

        <div v-if="presentation.environment?.length" class="table-scroll system-table">
          <table>
            <thead><tr>
              <th v-for="column in columns" :key="column.key">
                <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
              </th>
            </tr></thead>
            <tbody>
              <tr v-for="(row, index) in sortedRows" :key="`${row.item}-${index}`">
                <td>{{ row.item }}</td>
                <td><span class="status-pill" :class="row.status_class">{{ row.status }}</span></td>
                <td class="mono">{{ row.detail }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="presentation.memory?.length" class="table-scroll system-table">
          <table>
            <thead><tr><th>Пул</th><th>Total</th><th>Used</th><th>Free</th><th>Загрузка</th></tr></thead>
            <tbody>
              <tr v-for="row in presentation.memory" :key="row.pool">
                <td>{{ row.pool }}</td><td>{{ row.total || "—" }}</td><td>{{ row.used || "—" }}</td>
                <td>{{ row.free || "—" }}</td><td>{{ row.usage || row.detail || "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <section v-if="presentation.cpu?.length" class="source-section">
          <header><div><strong>CPU history</strong><code>show processes cpu history</code></div></header>
          <pre>{{ presentation.cpu.join("\n") }}</pre>
        </section>
      </div>

      <div v-else-if="presentation.kind === 'logs'" class="detail-output">
        <div class="detail-heading">
          <div>
            <span class="eyebrow">Логи</span>
            <strong>Показано {{ presentation.shown ?? 0 }} из {{ presentation.total ?? 0 }}</strong>
          </div>
          <div class="detail-states">
            <span>Лимит: {{ presentation.limit }}</span>
            <span v-if="presentation.filter">Фильтр: {{ presentation.filter }}</span>
          </div>
        </div>
        <div v-if="sortedRows.length" class="table-scroll logs-table">
          <table>
            <thead><tr>
              <th v-for="column in columns" :key="column.key">
                <button type="button" class="sort-button" @click="sortBy(column.key)">{{ column.label }} <span>{{ sortLabel(column.key) }}</span></button>
              </th>
            </tr></thead>
            <tbody>
              <tr v-for="(row, index) in sortedRows" :key="`${row.raw}-${index}`">
                <td>{{ row.severity || "—" }}</td>
                <td>{{ row.facility || "—" }}</td>
                <td>{{ row.mnemonic || "—" }}</td>
                <td class="mono">{{ row.message || row.raw }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <pre v-else class="terminal empty">Логов по заданным условиям не найдено.</pre>
      </div>
    </div>

    <pre v-else class="terminal" :class="{ empty: !output }">{{ output || "После подключения выбери действие слева. Результат появится здесь." }}</pre>
  </div>
</template>

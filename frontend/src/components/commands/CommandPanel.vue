<script setup lang="ts">
import { computed } from "vue";
import { commandOptions } from "../../data/commandOptions";
import type { CommandForm } from "../../types/netpanel";

defineProps<{ canRun: boolean; isBusy: boolean }>();
const emit = defineEmits<{ run: [] }>();
const command = defineModel<CommandForm>("command", { required: true });

const selectedOption = computed(() => commandOptions.find((item) => item.value === command.value.action));
const needsProtocol = computed(() => ["routing_table", "protocol_neighbors"].includes(command.value.action));
const needsMac = computed(() => command.value.action === "mac_on_interface");
const needsRoute = computed(() => command.value.action === "route_lookup");
const needsDiscovery = computed(() => command.value.action === "discovery_neighbors");
const needsInterfaces = computed(() => command.value.action === "interface_diagnostics");
const needsMacTable = computed(() => command.value.action === "mac_table");
const needsIpLocation = computed(() => command.value.action === "ip_location");
const needsReachability = computed(() => command.value.action === "reachability");
const needsLogs = computed(() => command.value.action === "logs");
</script>

<template>
  <section class="panel">
    <div class="panel-head">
      <h2>Действие</h2>
      <span>{{ selectedOption?.description }}</span>
    </div>
    <label>
      Команда
      <select v-model="command.action">
        <option v-for="option in commandOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
    </label>

    <div v-if="needsProtocol" class="segmented">
      <button type="button" :class="{ active: command.protocol === 'bgp' }" @click="command.protocol = 'bgp'">BGP</button>
      <button type="button" :class="{ active: command.protocol === 'ospf' }" @click="command.protocol = 'ospf'">OSPF</button>
    </div>
    <div v-if="needsDiscovery" class="segmented">
      <button type="button" :class="{ active: command.discovery_protocol === 'both' }" @click="command.discovery_protocol = 'both'">CDP + LLDP</button>
      <button type="button" :class="{ active: command.discovery_protocol === 'cdp' }" @click="command.discovery_protocol = 'cdp'">CDP</button>
      <button type="button" :class="{ active: command.discovery_protocol === 'lldp' }" @click="command.discovery_protocol = 'lldp'">LLDP</button>
    </div>
    <div v-if="needsInterfaces" class="segmented">
      <button type="button" :class="{ active: command.interface_view === 'status' }" @click="command.interface_view = 'status'">Статус</button>
      <button type="button" :class="{ active: command.interface_view === 'summary' }" @click="command.interface_view = 'summary'">Сводка</button>
      <button type="button" :class="{ active: command.interface_view === 'detail' }" @click="command.interface_view = 'detail'">Интерфейс</button>
    </div>

    <label v-if="needsInterfaces && command.interface_view === 'detail'">
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
      <label>MAC-адрес<input v-model="command.mac_address" placeholder="0011.2233.4455" autocomplete="off" /></label>
      <label>VLAN<input v-model.number="command.vlan" type="number" min="1" max="4094" placeholder="10" /></label>
    </div>
    <label v-if="needsMacTable" class="check">
      <input v-model="command.dynamic_only" type="checkbox" /> Только динамические записи
    </label>
    <label v-if="needsRoute">Адрес или CIDR<input v-model="command.route_query" placeholder="10.10.10.0/24" autocomplete="off" /></label>
    <label v-if="needsIpLocation">IP-адрес<input v-model="command.ip_address" placeholder="10.10.10.25" autocomplete="off" /></label>
    <div v-if="needsReachability" class="segmented">
      <button type="button" :class="{ active: command.reachability_mode === 'ping' }" @click="command.reachability_mode = 'ping'">Ping</button>
      <button type="button" :class="{ active: command.reachability_mode === 'traceroute' }" @click="command.reachability_mode = 'traceroute'">Traceroute</button>
    </div>
    <label v-if="needsReachability">
      IP-адрес
      <input v-model="command.ip_address" placeholder="10.10.10.25" autocomplete="off" />
    </label>
    <label v-if="needsReachability && command.reachability_mode === 'ping'">
      Source interface
      <input v-model="command.source_interface" placeholder="Vlan10" autocomplete="off" />
    </label>
    <div v-if="needsLogs" class="grid two">
      <label>Последние строки<input v-model.number="command.log_limit" type="number" min="1" max="1000" placeholder="50" /></label>
      <label>Ключевое слово<input v-model="command.log_filter" placeholder="LINK, ERROR, DHCP" autocomplete="off" /></label>
    </div>
    <label v-if="needsDiscovery || command.action === 'protocol_neighbors'" class="check">
      <input v-model="command.detail" type="checkbox" /> Подробный вывод
    </label>
    <button class="run" type="button" :disabled="!canRun" @click="emit('run')">
      {{ isBusy ? "Выполняю..." : "Выполнить" }}
    </button>
  </section>
</template>

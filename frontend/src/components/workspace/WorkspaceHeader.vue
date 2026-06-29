<script setup lang="ts">
import type { Workspace } from "../../types/netpanel";

defineProps<{ connectedTo: string; commands: string[] }>();
const workspace = defineModel<Workspace>("workspace", { required: true });
</script>

<template>
  <header class="topbar">
    <div>
      <span class="eyebrow">Сессия</span>
      <strong>{{ connectedTo || "нет подключения" }}</strong>
    </div>
    <div class="workspace-tabs">
      <button type="button" :class="{ active: workspace === 'commands' }" @click="workspace = 'commands'">Команды</button>
      <button type="button" :class="{ active: workspace === 'terminal' }" @click="workspace = 'terminal'">Терминал</button>
    </div>
    <div v-if="workspace === 'commands' && commands.length" class="command-list">
      <code v-for="item in commands" :key="item">{{ item }}</code>
    </div>
  </header>
</template>

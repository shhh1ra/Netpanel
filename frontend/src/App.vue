<script setup lang="ts">
import { writeText } from "@tauri-apps/api/clipboard";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import CommandPanel from "./components/commands/CommandPanel.vue";
import ConnectionPanel from "./components/connection/ConnectionPanel.vue";
import ResultsPane from "./components/workspace/ResultsPane.vue";
import TerminalPane from "./components/workspace/TerminalPane.vue";
import WorkspaceHeader from "./components/workspace/WorkspaceHeader.vue";
import { useBackendSidecar } from "./composables/useBackendSidecar";
import { useCommands } from "./composables/useCommands";
import { useProfiles } from "./composables/useProfiles";
import { useSession } from "./composables/useSession";
import { useTerminal } from "./composables/useTerminal";
import { useUpdateCheck } from "./composables/useUpdateCheck";
import type { ConnectionForm, Workspace } from "./types/netpanel";

const apiBase = ref("http://127.0.0.1:17761");
const workspace = ref<Workspace>("commands");
const sessionId = ref("");
const connectedTo = ref("");
const isBusy = ref(false);
const error = ref("");
const copied = ref(false);
const passwordField = ref<HTMLInputElement | null>(null);
const terminalPane = ref<{ host: HTMLElement | null } | null>(null);
const connection = reactive<ConnectionForm>({
  host: "",
  port: 22,
  username: "",
  password: "",
  authType: "password",
  keyPath: "",
});
const isConnected = computed(() => Boolean(sessionId.value));

const terminal = useTerminal({ apiBase, sessionId, workspace, error });
const backend = useBackendSidecar();
const updates = useUpdateCheck();

async function focusPassword() {
  await nextTick();
  passwordField.value?.focus();
}

const session = useSession({
  apiBase,
  connection,
  workspace,
  sessionId,
  connectedTo,
  isBusy,
  error,
  closeTerminal: terminal.close,
  openTerminal: terminal.open,
  resetTerminal: terminal.reset,
  focusPassword,
});

const profiles = useProfiles({
  connection,
  isConnected,
  connect: session.connect,
  disconnect: session.disconnect,
  focusPassword,
});

const commands = useCommands({
  apiBase,
  sessionId,
  isBusy,
  isConnected,
  error,
  workspace,
  closeTerminal: terminal.close,
});

async function connect() {
  commands.output.value = "";
  commands.presentation.value = null;
  await session.connect();
}

async function copyOutput() {
  const text = workspace.value === "terminal" ? terminal.text() : commands.output.value;
  if (!text) return;
  await writeText(text);
  copied.value = true;
  window.setTimeout(() => { copied.value = false; }, 1200);
}

async function restartBackend() {
  error.value = "";
  isBusy.value = true;
  await terminal.close();
  await backend.restart();
  sessionId.value = "";
  connectedTo.value = "";
  isBusy.value = false;
  if (backend.lastError.value) error.value = `Backend restart failed: ${backend.lastError.value}`;
}

onMounted(async () => {
  await profiles.load();
  void backend.start();
  updates.startAutoCheck();
  await nextTick();
  if (terminalPane.value?.host) terminal.mount(terminalPane.value.host);
});

watch(workspace, async (value) => {
  if (value === "terminal") {
    await nextTick();
    terminal.fit();
    terminal.open();
    terminal.focus();
  } else {
    await terminal.close();
  }
});

onBeforeUnmount(() => {
  updates.stopAutoCheck();
  terminal.dispose();
  void backend.stop();
});
</script>

<template>
  <main class="shell">
    <aside class="side">
      <header class="brand">
        <div class="mark">2960</div>
        <div>
          <h1>Netpanel <span>v{{ updates.currentVersion }}</span></h1>
          <p>SSH-панель для быстрых show-команд</p>
        </div>
      </header>

      <ConnectionPanel
        v-model:api-base="apiBase"
        v-model:connection="connection"
        v-model:selected-host-id="profiles.selectedId.value"
        v-model:profile-name="profiles.profileName.value"
        v-model:remember-password="profiles.rememberPassword.value"
        :profiles="profiles.profiles.value"
        :is-busy="isBusy"
        :is-connected="isConnected"
        :backend-restarting="backend.isRestarting.value"
        @connect="connect"
        @disconnect="session.disconnect"
        @restart-backend="restartBackend"
        @select-profile="profiles.select"
        @save-profile="profiles.save"
        @delete-profile="profiles.remove"
        @password-element="passwordField = $event"
      />

      <CommandPanel
        v-model:command="commands.command"
        :can-run="commands.canRun.value"
        :is-busy="isBusy"
        @run="commands.run"
      />
    </aside>

    <section class="workspace">
      <WorkspaceHeader
        v-model:workspace="workspace"
        :connected-to="connectedTo"
        :commands="commands.issued.value"
      />
      <div v-if="updates.hasUpdate.value" class="notice update">
        <span>Доступна версия {{ updates.latestVersion.value }}. Сейчас установлена {{ updates.currentVersion }}.</span>
        <button type="button" @click="updates.openRelease">Открыть релиз</button>
        <button type="button" class="ghost" @click="updates.dismiss">Скрыть</button>
      </div>
      <div v-if="error" class="notice error">{{ error }}</div>
      <ResultsPane
        v-show="workspace === 'commands'"
        v-model:mode="commands.mode.value"
        :output="commands.output.value"
        :presentation="commands.presentation.value"
        :copied="copied"
        @copy="copyOutput"
      />
      <TerminalPane
        v-show="workspace === 'terminal'"
        ref="terminalPane"
        :copied="copied"
        @copy="copyOutput"
      />
    </section>
  </main>
</template>

import { computed, type Ref } from "vue";
import type { ConnectionForm, Workspace } from "../types/netpanel";
import { errorMessage, parseResponse } from "../services/api";

export function useSession(options: {
  apiBase: Ref<string>;
  connection: ConnectionForm;
  workspace: Ref<Workspace>;
  sessionId: Ref<string>;
  connectedTo: Ref<string>;
  isBusy: Ref<boolean>;
  error: Ref<string>;
  closeTerminal: () => Promise<void>;
  openTerminal: () => void;
  resetTerminal: () => void;
  focusPassword: () => Promise<void>;
}) {
  const isConnected = computed(() => Boolean(options.sessionId.value));

  async function connect() {
    if (!options.connection.password) {
      options.error.value = "Введите пароль для подключения";
      await options.focusPassword();
      return;
    }
    options.error.value = "";
    options.isBusy.value = true;
    options.resetTerminal();
    try {
      const response = await fetch(`${options.apiBase.value}/sessions`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(options.connection),
      });
      const data = await parseResponse(response);
      options.sessionId.value = data.session_id;
      options.connectedTo.value = `${data.username}@${data.host}`;
      if (options.workspace.value === "terminal") options.openTerminal();
    } catch (cause) {
      options.error.value = errorMessage(cause);
    } finally {
      options.isBusy.value = false;
    }
  }

  async function disconnect() {
    if (!options.sessionId.value) return;
    options.isBusy.value = true;
    options.error.value = "";
    await options.closeTerminal();
    try {
      await fetch(`${options.apiBase.value}/sessions/${options.sessionId.value}`, { method: "DELETE" });
    } finally {
      options.sessionId.value = "";
      options.connectedTo.value = "";
      options.isBusy.value = false;
    }
  }

  return { isConnected, connect, disconnect };
}

import { Command, type Child } from "@tauri-apps/api/shell";
import { ref } from "vue";

export function useBackendSidecar() {
  let child: Child | null = null;
  const isRestarting = ref(false);
  const lastError = ref("");

  async function start() {
    if (child) return;
    try {
      const command = Command.sidecar("../sidecars/netpanel-backend", [], {
        env: {
          CISCO_CLIENT_HOST: "127.0.0.1",
          CISCO_CLIENT_PORT: "17761",
        },
      });
      child = await command.spawn();
      lastError.value = "";
    } catch (error) {
      console.warn("Bundled backend was not started", error);
      lastError.value = error instanceof Error ? error.message : String(error);
    }
  }

  async function stop() {
    const running = child;
    child = null;
    if (!running) return;
    try {
      await running.kill();
    } catch (error) {
      console.warn("Bundled backend was not stopped cleanly", error);
    }
  }

  async function restart() {
    isRestarting.value = true;
    try {
      await stop();
      await start();
    } finally {
      isRestarting.value = false;
    }
  }

  return { start, stop, restart, isRestarting, lastError };
}

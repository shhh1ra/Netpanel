import { Command, type Child } from "@tauri-apps/api/shell";

export function useBackendSidecar() {
  let child: Child | null = null;

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
    } catch (error) {
      console.warn("Bundled backend was not started", error);
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

  return { start, stop };
}

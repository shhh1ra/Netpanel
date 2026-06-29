import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import type { Ref } from "vue";
import type { Workspace } from "../types/netpanel";

export function useTerminal(options: {
  apiBase: Ref<string>;
  sessionId: Ref<string>;
  workspace: Ref<Workspace>;
  error: Ref<string>;
}) {
  let terminal: Terminal | null = null;
  let fitAddon: FitAddon | null = null;
  let socket: WebSocket | null = null;
  let resizeObserver: ResizeObserver | null = null;

  function mount(host: HTMLElement) {
    if (terminal) return;
    terminal = new Terminal({
      cursorBlink: true,
      cursorStyle: "block",
      fontFamily: '"Cascadia Mono", "SFMono-Regular", Consolas, monospace',
      fontSize: 14,
      scrollback: 5000,
      theme: {
        background: "#030506", foreground: "#d7e3e7", cursor: "#7de4ef",
        selectionBackground: "#17434a", black: "#030506", brightBlack: "#68767c",
        cyan: "#55d4e3", brightCyan: "#a9f4fb", green: "#5be0a9",
        red: "#ff7e78", yellow: "#ffb866",
      },
    });
    fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(host);
    terminal.onData((data) => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "input", data }));
    });
    terminal.onResize(({ cols, rows }) => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "resize", columns: cols, rows }));
      }
    });
    resizeObserver = new ResizeObserver(fit);
    resizeObserver.observe(host);
  }

  function fit() {
    if (!fitAddon || options.workspace.value !== "terminal") return;
    try { fitAddon.fit(); } catch { /* Pane can be hidden during a Vue transition. */ }
  }

  function open() {
    if (!options.sessionId.value || options.workspace.value !== "terminal") return;
    if (socket && socket.readyState <= WebSocket.OPEN) return;
    const websocketBase = options.apiBase.value.replace(/^http/, "ws");
    const current = new WebSocket(`${websocketBase}/sessions/${options.sessionId.value}/terminal/ws`);
    socket = current;
    current.addEventListener("open", () => {
      fit();
      current.send(JSON.stringify({ type: "resize", columns: terminal?.cols || 120, rows: terminal?.rows || 40 }));
      terminal?.focus();
    });
    current.addEventListener("message", (event) => {
      try {
        const message = JSON.parse(String(event.data));
        if (message.type === "output") terminal?.write(String(message.data || ""));
      } catch {
        terminal?.write(String(event.data));
      }
    });
    current.addEventListener("close", () => { if (socket === current) socket = null; });
    current.addEventListener("error", () => { options.error.value = "Не удалось открыть WebSocket-терминал"; });
  }

  async function close() {
    const current = socket;
    if (!current) return;
    socket = null;
    if (current.readyState === WebSocket.CLOSED) return;
    await new Promise<void>((resolve) => {
      const timeout = window.setTimeout(resolve, 500);
      current.addEventListener("close", () => { window.clearTimeout(timeout); resolve(); }, { once: true });
      current.close();
    });
  }

  function reset() { terminal?.reset(); }
  function focus() { terminal?.focus(); }

  function text() {
    if (!terminal) return "";
    const buffer = terminal.buffer.active;
    const lines = [];
    for (let index = 0; index < buffer.length; index += 1) {
      lines.push(buffer.getLine(index)?.translateToString(true) || "");
    }
    return lines.join("\n").trimEnd();
  }

  function dispose() {
    resizeObserver?.disconnect();
    socket?.close();
    terminal?.dispose();
  }

  return { mount, fit, open, close, reset, focus, text, dispose };
}

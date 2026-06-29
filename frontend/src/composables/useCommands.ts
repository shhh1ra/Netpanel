import { computed, reactive, ref, type ComputedRef, type Ref } from "vue";
import type { CommandForm, Presentation, ResultMode, Workspace } from "../types/netpanel";
import { errorMessage, parseResponse } from "../services/api";

export function useCommands(options: {
  apiBase: Ref<string>; sessionId: Ref<string>; isBusy: Ref<boolean>;
  isConnected: ComputedRef<boolean>; error: Ref<string>; workspace: Ref<Workspace>;
  closeTerminal: () => Promise<void>;
}) {
  const output = ref("");
  const presentation = ref<Presentation | null>(null);
  const mode = ref<ResultMode>("human");
  const issued = ref<string[]>([]);
  const command = reactive<CommandForm>({
    action: "running_config", protocol: "bgp", discovery_protocol: "both",
    mac_address: "", interface: "", route_query: "", interface_view: "status",
    vlan: null, dynamic_only: false, ip_address: "", source_interface: "",
    reachability_mode: "ping", log_limit: 50, log_filter: "", detail: false,
  });

  const canRun = computed(() => {
    if (!options.isConnected.value || options.isBusy.value) return false;
    if (command.action === "interface_diagnostics" && command.interface_view === "detail") return Boolean(command.interface.trim());
    if (command.action === "ip_location") return Boolean(command.ip_address.trim());
    if (command.action === "reachability") return Boolean(command.ip_address.trim());
    return true;
  });

  async function run() {
    if (!options.sessionId.value) return;
    await options.closeTerminal();
    options.error.value = ""; output.value = ""; presentation.value = null; issued.value = [];
    options.workspace.value = "commands"; options.isBusy.value = true;
    const protocolNeeded = ["routing_table", "protocol_neighbors"].includes(command.action);
    try {
      const response = await fetch(`${options.apiBase.value}/sessions/${options.sessionId.value}/commands`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: command.action, protocol: protocolNeeded ? command.protocol : null,
          discovery_protocol: command.discovery_protocol, mac_address: command.mac_address || null,
          interface: command.interface || null, route_query: command.route_query || null,
          interface_view: command.interface_view, vlan: command.vlan || null,
          dynamic_only: command.dynamic_only, ip_address: command.ip_address || null,
          source_interface: command.source_interface || null,
          reachability_mode: command.reachability_mode,
          log_limit: command.log_limit || 50, log_filter: command.log_filter || null,
          detail: command.detail,
        }),
      });
      const data = await parseResponse(response);
      issued.value = data.commands;
      output.value = data.output || "Команда выполнена без текстового вывода.";
      presentation.value = data.presentation || null;
      mode.value = presentation.value ? "human" : "raw";
    } catch (cause) {
      options.error.value = errorMessage(cause);
    } finally {
      options.isBusy.value = false;
    }
  }

  async function runInterfaceDetail(interfaceName: string) {
    command.action = "interface_diagnostics";
    command.interface_view = "detail";
    command.interface = interfaceName;
    await run();
  }

  return { command, output, presentation, mode, issued, canRun, run, runInterfaceDetail };
}

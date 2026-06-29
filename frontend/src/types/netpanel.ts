export type Action =
  | "running_config" | "arp_table" | "mac_on_interface" | "routing_table"
  | "protocol_neighbors" | "static_routes" | "route_lookup" | "discovery_neighbors"
  | "interface_diagnostics" | "ip_interface_brief" | "mac_table" | "ip_location"
  | "reachability" | "system_monitoring" | "logs";

export type Protocol = "bgp" | "ospf";
export type DiscoveryProtocol = "cdp" | "lldp" | "both";
export type InterfaceView = "status" | "summary" | "detail";
export type ReachabilityMode = "ping" | "traceroute";
export type Workspace = "commands" | "terminal";
export type ResultMode = "human" | "raw";

export interface HostProfile {
  id: string; name: string; host: string; port: number; username: string; password: string;
  authType: "password" | "key"; keyPath?: string;
}

export interface ConnectionForm {
  host: string; port: number; username: string; password: string;
  authType: "password" | "key"; keyPath: string;
}

export interface CommandForm {
  action: Action; protocol: Protocol; discovery_protocol: DiscoveryProtocol;
  mac_address: string; interface: string; route_query: string;
  interface_view: InterfaceView; vlan: number | null; dynamic_only: boolean;
  ip_address: string; source_interface: string; reachability_mode: ReachabilityMode;
  log_limit: number; log_filter: string;
  detail: boolean;
}

export interface CommandOption { value: Action; label: string; description: string; }
export interface ResultMetric { label: string; value: string; }
export interface ResultSource {
  label: string; command: string; status: "found" | "empty" | "unsupported"; lines: string[];
}

export interface Presentation {
  kind: "interface_status" | "interface_summary" | "interface_detail"
    | "ip_interface_brief" | "mac_table" | "ip_location" | "reachability"
    | "system_monitoring" | "logs";
  rows?: Record<string, any>[];
  metrics?: ResultMetric[];
  sources?: ResultSource[];
  interface?: string;
  state?: string;
  protocol?: string;
  command?: string;
  mode?: string;
  status?: string;
  environment?: Record<string, any>[];
  cpu?: string[];
  memory?: Record<string, any>[];
  total?: number;
  shown?: number;
  limit?: number;
  filter?: string;
}

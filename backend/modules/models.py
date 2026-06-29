from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandAction(str, Enum):
    running_config = "running_config"
    arp_table = "arp_table"
    mac_on_interface = "mac_on_interface"
    routing_table = "routing_table"
    protocol_neighbors = "protocol_neighbors"
    static_routes = "static_routes"
    route_lookup = "route_lookup"
    discovery_neighbors = "discovery_neighbors"
    interface_diagnostics = "interface_diagnostics"
    ip_interface_brief = "ip_interface_brief"
    mac_table = "mac_table"
    ip_location = "ip_location"
    reachability = "reachability"
    system_monitoring = "system_monitoring"
    logs = "logs"


class RoutingProtocol(str, Enum):
    bgp = "bgp"
    ospf = "ospf"


class DiscoveryProtocol(str, Enum):
    cdp = "cdp"
    lldp = "lldp"
    both = "both"


class InterfaceView(str, Enum):
    status = "status"
    summary = "summary"
    detail = "detail"


class ReachabilityMode(str, Enum):
    ping = "ping"
    traceroute = "traceroute"


class ConnectRequest(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1)
    password: str = ""
    auth_type: Literal["password", "key"] = "password"
    key_path: str | None = None


class ConnectResponse(BaseModel):
    session_id: str
    host: str
    username: str


class CommandRequest(BaseModel):
    action: CommandAction
    protocol: RoutingProtocol | None = None
    discovery_protocol: DiscoveryProtocol = DiscoveryProtocol.both
    mac_address: str | None = None
    interface: str | None = None
    route_query: str | None = None
    interface_view: InterfaceView = InterfaceView.status
    vlan: int | None = Field(default=None, ge=1, le=4094)
    dynamic_only: bool = False
    ip_address: str | None = None
    source_interface: str | None = None
    reachability_mode: ReachabilityMode = ReachabilityMode.ping
    log_limit: int = Field(default=50, ge=1, le=1000)
    log_filter: str | None = Field(default=None, max_length=120)
    detail: bool = False


class CommandResponse(BaseModel):
    action: CommandAction
    commands: list[str]
    output: str
    presentation: dict[str, Any] | None = None


class TerminalRequest(BaseModel):
    command: str = Field(min_length=1, max_length=512)


class TerminalResponse(BaseModel):
    command: str
    output: str

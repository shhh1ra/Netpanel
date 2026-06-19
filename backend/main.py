from __future__ import annotations

import ipaddress
import re
from enum import Enum
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from modules.ssh.manager import SSHManager


class CommandAction(str, Enum):
    running_config = "running_config"
    arp_table = "arp_table"
    mac_on_interface = "mac_on_interface"
    routing_table = "routing_table"
    protocol_neighbors = "protocol_neighbors"
    static_routes = "static_routes"
    route_lookup = "route_lookup"
    discovery_neighbors = "discovery_neighbors"


class RoutingProtocol(str, Enum):
    bgp = "bgp"
    ospf = "ospf"


class DiscoveryProtocol(str, Enum):
    cdp = "cdp"
    lldp = "lldp"
    both = "both"


class ConnectRequest(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


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
    detail: bool = False


class CommandResponse(BaseModel):
    action: CommandAction
    commands: list[str]
    output: str


manager = SSHManager()
app = FastAPI(title="Cisco Client API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost", "https://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=ConnectResponse)
async def connect(payload: ConnectRequest):
    session_id = uuid4().hex
    session = manager.create_session(session_id)

    try:
        await session.connect(
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=payload.password,
        )
    except Exception as exc:
        manager.remove_session(session_id)
        raise HTTPException(status_code=502, detail=f"SSH connection failed: {exc}") from exc

    return ConnectResponse(session_id=session_id, host=payload.host, username=payload.username)


@app.delete("/sessions/{session_id}")
async def disconnect(session_id: str):
    await manager.close_session(session_id)
    return {"status": "disconnected"}


@app.post("/sessions/{session_id}/commands", response_model=CommandResponse)
async def run_action(session_id: str, payload: CommandRequest):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        raise HTTPException(status_code=404, detail="SSH session is not connected")

    commands = build_commands(payload)
    chunks = []
    for command in commands:
        try:
            result = await session.exec(command)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Command failed: {exc}") from exc
        chunks.append(f"$ {command}\n{result}".strip())

    return CommandResponse(action=payload.action, commands=commands, output="\n\n".join(chunks))


def build_commands(payload: CommandRequest) -> list[str]:
    if payload.action == CommandAction.running_config:
        return ["show running-config"]

    if payload.action == CommandAction.arp_table:
        return ["show ip arp"]

    if payload.action == CommandAction.mac_on_interface:
        mac = normalize_mac(payload.mac_address)
        commands = [f"show mac address-table address {mac}"]
        if payload.interface:
            commands.append(f"show mac address-table interface {sanitize_interface(payload.interface)}")
        return commands

    if payload.action == CommandAction.routing_table:
        protocol = require_protocol(payload.protocol)
        if protocol == RoutingProtocol.bgp:
            return ["show ip bgp summary", "show ip bgp"]
        return ["show ip ospf", "show ip route ospf"]

    if payload.action == CommandAction.protocol_neighbors:
        protocol = require_protocol(payload.protocol)
        if protocol == RoutingProtocol.bgp:
            return ["show ip bgp summary", "show ip bgp neighbors"]
        return ["show ip ospf neighbor detail" if payload.detail else "show ip ospf neighbor"]

    if payload.action == CommandAction.static_routes:
        return ["show ip route static"]

    if payload.action == CommandAction.route_lookup:
        query = normalize_route_query(payload.route_query)
        return [f"show ip route {query}"]

    if payload.action == CommandAction.discovery_neighbors:
        detail = " detail" if payload.detail else ""
        if payload.discovery_protocol == DiscoveryProtocol.cdp:
            return [f"show cdp neighbors{detail}"]
        if payload.discovery_protocol == DiscoveryProtocol.lldp:
            return [f"show lldp neighbors{detail}"]
        return [f"show cdp neighbors{detail}", f"show lldp neighbors{detail}"]

    raise HTTPException(status_code=400, detail="Unsupported action")


def require_protocol(protocol: RoutingProtocol | None) -> RoutingProtocol:
    if not protocol:
        raise HTTPException(status_code=422, detail="Protocol is required")
    return protocol


def normalize_mac(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=422, detail="MAC address is required")

    compact = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(compact) != 12:
        raise HTTPException(status_code=422, detail="MAC address must contain 12 hex digits")

    return ".".join(compact[i : i + 4] for i in range(0, 12, 4)).lower()


def sanitize_interface(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9/.\- ]{0,48}", value):
        raise HTTPException(status_code=422, detail="Interface contains unsupported characters")
    return value.strip()


def normalize_route_query(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=422, detail="Route address or network is required")

    raw = value.strip()
    try:
        if "/" in raw:
            network = ipaddress.ip_network(raw, strict=False)
            return f"{network.network_address} {network.netmask}"
        return str(ipaddress.ip_address(raw))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Route query must be an IP address or CIDR") from exc

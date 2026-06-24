from __future__ import annotations

import asyncio
import ipaddress
import re
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
    interface_diagnostics = "interface_diagnostics"
    ip_interface_brief = "ip_interface_brief"
    mac_table = "mac_table"
    ip_location = "ip_location"


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
    interface_view: InterfaceView = InterfaceView.status
    vlan: int | None = Field(default=None, ge=1, le=4094)
    dynamic_only: bool = False
    ip_address: str | None = None
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


manager = SSHManager()
app = FastAPI(title="Netpanel API", version="1.3.0")

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
    results = []
    for command in commands:
        try:
            result = await session.exec(command)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Command failed: {exc}") from exc
        results.append(result)
        chunks.append(f"$ {command}\n{result}".strip())

    return CommandResponse(
        action=payload.action,
        commands=commands,
        output="\n\n".join(chunks),
        presentation=build_presentation(payload, commands, results),
    )


@app.post("/sessions/{session_id}/terminal", response_model=TerminalResponse)
async def run_terminal_command(session_id: str, payload: TerminalRequest):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        raise HTTPException(status_code=404, detail="SSH session is not connected")

    command = payload.command.strip()
    try:
        result = await session.terminal(command)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Terminal command failed: {exc}") from exc

    return TerminalResponse(command=command, output=result)


@app.post("/sessions/{session_id}/terminal/interrupt")
async def interrupt_terminal(session_id: str):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        raise HTTPException(status_code=404, detail="SSH session is not connected")

    try:
        session.interrupt()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Terminal interrupt failed: {exc}") from exc
    return {"status": "interrupted"}


@app.websocket("/sessions/{session_id}/terminal/ws")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    session = manager.get_session(session_id)
    if not session or not session.is_connected:
        await websocket.close(code=4404, reason="SSH session is not connected")
        return

    await websocket.accept()
    try:
        prompt = await session.attach_terminal()
    except Exception as exc:
        await websocket.close(code=4409, reason=str(exc))
        return

    async def receive_input():
        try:
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "input":
                    session.terminal_write(str(message.get("data", "")))
                elif message_type == "resize":
                    columns = max(20, min(500, int(message.get("columns", 120))))
                    rows = max(5, min(200, int(message.get("rows", 40))))
                    session.resize_terminal(columns, rows)
        except WebSocketDisconnect:
            return

    async def send_output():
        try:
            if prompt:
                await websocket.send_json({"type": "output", "data": prompt})
            while True:
                data = await session.terminal_read()
                if not data:
                    return
                await websocket.send_json({"type": "output", "data": data})
        except WebSocketDisconnect:
            return

    input_task = asyncio.create_task(receive_input())
    output_task = asyncio.create_task(send_output())
    try:
        done, pending = await asyncio.wait(
            {input_task, output_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        session.detach_terminal()


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

    if payload.action == CommandAction.interface_diagnostics:
        if payload.interface_view == InterfaceView.status:
            return ["show interfaces status"]
        if payload.interface_view == InterfaceView.summary:
            return ["show interfaces summary"]
        if not payload.interface:
            raise HTTPException(status_code=422, detail="Interface is required for detailed diagnostics")
        return [f"show interfaces {sanitize_interface(payload.interface)}"]

    if payload.action == CommandAction.ip_interface_brief:
        return ["show ip interface brief"]

    if payload.action == CommandAction.mac_table:
        commands = []
        if payload.mac_address:
            commands.append(f"show mac address-table address {normalize_mac(payload.mac_address)}")
        if payload.vlan is not None:
            suffix = " dynamic" if payload.dynamic_only else ""
            suffix += f" vlan {payload.vlan}"
            commands.append(f"show mac address-table{suffix}")
        if not commands:
            suffix = " dynamic" if payload.dynamic_only else ""
            commands.append(f"show mac address-table{suffix}")
        return commands

    if payload.action == CommandAction.ip_location:
        ip = normalize_ip_address(payload.ip_address)
        return [
            f"show ip arp | include {ip}",
            f"show ip dhcp snooping binding | include {ip}",
            f"show ip device tracking | include {ip}",
        ]

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


def normalize_ip_address(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=422, detail="IP address is required")

    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="A valid IP address is required") from exc


def build_presentation(payload: CommandRequest, commands: list[str], results: list[str]) -> dict[str, Any] | None:
    if not results:
        return None

    if payload.action == CommandAction.interface_diagnostics:
        if payload.interface_view == InterfaceView.status:
            rows = parse_interface_status(results[0])
            return {"kind": "interface_status", "rows": rows} if rows else None
        if payload.interface_view == InterfaceView.summary:
            rows = parse_interface_summary(results[0])
            return {"kind": "interface_summary", "rows": rows} if rows else None
        details = parse_interface_detail(results[0])
        return {"kind": "interface_detail", **details} if details else None

    if payload.action == CommandAction.ip_interface_brief:
        rows = parse_ip_interface_brief(results[0])
        return {"kind": "ip_interface_brief", "rows": rows} if rows else None

    if payload.action in {CommandAction.mac_table, CommandAction.mac_on_interface}:
        rows = []
        for result in results:
            rows.extend(parse_mac_table(result))
        return {"kind": "mac_table", "rows": rows} if rows else None

    if payload.action == CommandAction.ip_location:
        labels = ["ARP", "DHCP Snooping", "IP Device Tracking"]
        sources = []
        for label, command, result in zip(labels, commands, results):
            clean_lines = [line.strip() for line in result.splitlines() if line.strip()]
            unsupported = any(line.startswith("%") for line in clean_lines)
            sources.append(
                {
                    "label": label,
                    "command": command,
                    "status": "unsupported" if unsupported else ("found" if clean_lines else "empty"),
                    "lines": clean_lines,
                }
            )
        return {"kind": "ip_location", "sources": sources}

    return None


def parse_interface_status(output: str) -> list[dict[str, Any]]:
    lines = output.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if "Port" in line and "Status" in line and "Vlan" in line),
        None,
    )
    if header_index is None:
        return []

    header = lines[header_index]
    column_names = ["port", "name", "status", "vlan", "duplex", "speed", "type"]
    labels = ["Port", "Name", "Status", "Vlan", "Duplex", "Speed", "Type"]
    starts = [header.find(label) for label in labels]
    if any(start < 0 for start in starts):
        return []

    rows = []
    for line in lines[header_index + 1 :]:
        if not line.strip() or set(line.strip()) <= {"-", " "}:
            continue
        values = {}
        for index, name in enumerate(column_names):
            end = starts[index + 1] if index + 1 < len(starts) else None
            values[name] = line[starts[index] : end].strip()
        if values["port"] and re.match(r"^[A-Za-z]", values["port"]):
            values["up"] = values["status"].lower() == "connected"
            rows.append(values)
    return rows


def parse_interface_summary(output: str) -> list[dict[str, Any]]:
    lines = output.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if "Interface" in line and "RXBS" in line and "TXBS" in line),
        None,
    )
    if header_index is None:
        return []

    rows = []
    for line in lines[header_index + 1 :]:
        stripped = line.strip()
        if not stripped or set(stripped) <= {"-", " "}:
            continue
        up = stripped.startswith("*")
        parts = stripped.lstrip("*").strip().split()
        if len(parts) < 10 or not re.match(r"^[A-Za-z]", parts[0]):
            continue
        try:
            numbers = [int(value) for value in parts[1:10]]
        except ValueError:
            continue
        rows.append(
            {
                "interface": parts[0],
                "up": up,
                "input_hold": numbers[0],
                "input_drops": numbers[1],
                "output_hold": numbers[2],
                "output_drops": numbers[3],
                "rx_bps": numbers[4],
                "rx_pps": numbers[5],
                "tx_bps": numbers[6],
                "tx_pps": numbers[7],
                "throttle": numbers[8],
            }
        )
    return rows


def parse_interface_detail(output: str) -> dict[str, Any] | None:
    details: dict[str, Any] = {"metrics": []}
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    state_match = re.match(r"^(\S+) is ([^,]+), line protocol is (.+)$", first_line)
    if state_match:
        details.update(
            {
                "interface": state_match.group(1),
                "state": state_match.group(2).strip(),
                "protocol": state_match.group(3).strip(),
            }
        )

    patterns = [
        (r"Hardware is ([^,]+)(?:, address is ([0-9a-fA-F.:-]+))?", ("Оборудование", "MAC-адрес")),
        (r"MTU (\d+) bytes, BW (\d+) Kbit/sec, DLY (\d+) usec", ("MTU", "Пропускная способность", "Задержка")),
        (r"reliability (\d+/\d+), txload (\d+/\d+), rxload (\d+/\d+)", ("Надёжность", "Загрузка TX", "Загрузка RX")),
        (r"5 minute input rate (\d+) bits/sec, (\d+) packets/sec", ("Входящий трафик", "Входящие пакеты")),
        (r"5 minute output rate (\d+) bits/sec, (\d+) packets/sec", ("Исходящий трафик", "Исходящие пакеты")),
        (r"(\d+) input errors, (\d+) CRC", ("Ошибки входа", "Ошибки CRC")),
        (r"(\d+) output errors, (\d+) collisions", ("Ошибки выхода", "Коллизии")),
    ]
    for pattern, labels in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if not match:
            continue
        for label, value in zip(labels, match.groups()):
            if value is not None:
                details["metrics"].append({"label": label, "value": value})

    return details if details.get("interface") or details["metrics"] else None


def parse_ip_interface_brief(output: str) -> list[dict[str, Any]]:
    rows = []
    pattern = re.compile(
        r"^\s*(?P<interface>\S+)\s+(?P<ip_address>\S+)\s+(?P<ok>YES|NO|\?)\s+"
        r"(?P<method>\S+)\s+(?P<status>.+?)\s+(?P<protocol>up|down)\s*$",
        re.IGNORECASE,
    )
    for line in output.splitlines():
        match = pattern.match(line)
        if not match or match.group("interface").lower() == "interface":
            continue
        row = match.groupdict()
        row["up"] = row["status"].lower() == "up" and row["protocol"].lower() == "up"
        rows.append(row)
    return rows


def parse_mac_table(output: str) -> list[dict[str, str]]:
    rows = []
    pattern = re.compile(
        r"^\s*\*?\s*(?P<vlan>\d+|All)\s+(?P<mac>[0-9a-fA-F.:-]{12,17})\s+"
        r"(?P<entry_type>[A-Za-z]+)\s+(?P<port>.+?)\s*$"
    )
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            rows.append(match.groupdict())
    return rows

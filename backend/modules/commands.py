from __future__ import annotations

from fastapi import HTTPException

from modules.models import CommandAction, CommandRequest, DiscoveryProtocol, InterfaceView, ReachabilityMode, RoutingProtocol
from modules.normalizers import (
    normalize_ip_address,
    normalize_mac,
    normalize_route_query,
    require_protocol,
    sanitize_interface,
)


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

    if payload.action == CommandAction.reachability:
        ip = normalize_ip_address(payload.ip_address)
        if payload.reachability_mode == ReachabilityMode.traceroute:
            return [f"traceroute {ip}"]
        if payload.source_interface:
            return [f"ping {ip} source {sanitize_interface(payload.source_interface)}"]
        return [f"ping {ip}"]

    if payload.action == CommandAction.system_monitoring:
        return [
            "show version",
            "show environment",
            "show env all",
            "show processes cpu history",
            "show memory statistics",
        ]

    if payload.action == CommandAction.logs:
        return ["show logging"]

    raise HTTPException(status_code=400, detail="Unsupported action")

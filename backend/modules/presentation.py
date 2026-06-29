from __future__ import annotations

from typing import Any

from modules.models import CommandAction, CommandRequest, InterfaceView
from modules.parsers import (
    parse_interface_detail,
    parse_interface_status,
    parse_interface_summary,
    parse_ip_interface_brief,
    parse_ip_location,
    parse_logs,
    parse_mac_table,
    parse_reachability,
    parse_system_monitoring,
)


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
        labels = ["ARP", "DHCP Snooping", "IP Device Tracking", "CAM"]
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
        return {"kind": "ip_location", "sources": sources, "rows": parse_ip_location(sources)}

    if payload.action == CommandAction.reachability:
        data = parse_reachability(results[0], commands[0])
        return {"kind": "reachability", "command": commands[0], **data}

    if payload.action == CommandAction.system_monitoring:
        return {"kind": "system_monitoring", **parse_system_monitoring(results)}

    if payload.action == CommandAction.logs:
        return {"kind": "logs", **parse_logs(results[0], payload.log_limit, payload.log_filter)}

    return None

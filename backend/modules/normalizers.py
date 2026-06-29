from __future__ import annotations

import ipaddress
import re

from fastapi import HTTPException

from modules.models import RoutingProtocol


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

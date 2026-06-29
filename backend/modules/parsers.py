from __future__ import annotations

import re
from typing import Any

from modules.normalizers import normalize_ip_address, normalize_mac


def find_mac_for_ip(results: list[str], ip_address: str | None) -> str | None:
    if not ip_address:
        return None

    ip = normalize_ip_address(ip_address)
    for result in results:
        for line in result.splitlines():
            if ip not in line:
                continue
            mac = find_mac_in_line(line)
            if mac:
                return mac
    return None


def find_mac_in_line(line: str) -> str | None:
    patterns = [
        r"(?i)\b[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\b",
        r"(?i)\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b",
        r"(?i)\b[0-9a-f]{2}(?:-[0-9a-f]{2}){5}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            return normalize_mac(match.group(0))
    return None


def parse_interface_status(output: str) -> list[dict[str, Any]]:
    lines = output.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if "Port" in line and "Status" in line and "Vlan" in line),
        None,
    )
    if header_index is None:
        return []

    status_pattern = (
        "connected|notconnect|disabled|err-disabled|inactive|monitoring|suspended|"
        "notpresent|sfpAbsent|xcvrAbsent|unknown"
    )
    row_pattern = re.compile(
        rf"^\s*(?P<port>\S+)\s+(?:(?P<name>.*?)\s+)?"
        rf"(?P<status>{status_pattern})\s+"
        r"(?P<vlan>\S+)\s+(?P<duplex>\S+)\s+(?P<speed>\S+)\s+(?P<type>.+?)\s*$",
        re.IGNORECASE,
    )
    rows = []
    for line in lines[header_index + 1 :]:
        if not line.strip() or set(line.strip()) <= {"-", " "}:
            continue
        match = row_pattern.match(line)
        if not match:
            continue
        values = match.groupdict()
        values["name"] = values.get("name") or ""
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


def parse_ip_location(sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in sources:
        if source.get("status") == "unsupported":
            continue
        label = str(source.get("label", ""))
        for line in source.get("lines", []):
            row = parse_ip_location_line(label, line)
            if row:
                rows.append(row)
    return rows


def parse_ip_location_line(source: str, line: str) -> dict[str, str] | None:
    mac = find_mac_in_line(line)
    ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)

    if source == "CAM":
        mac_rows = parse_mac_table(line)
        if not mac_rows:
            return None
        mac_row = mac_rows[0]
        return {
            "source": source,
            "ip_address": "",
            "mac": mac_row["mac"],
            "vlan": mac_row["vlan"],
            "port": mac_row["port"],
            "entry_type": mac_row["entry_type"],
        }

    if not mac and not ip_match:
        return None

    parts = line.split()
    row = {
        "source": source,
        "ip_address": ip_match.group(0) if ip_match else "",
        "mac": mac or "",
        "vlan": "",
        "port": "",
        "entry_type": "",
    }

    if source == "ARP":
        if len(parts) >= 6:
            row["entry_type"] = parts[-2]
            row["port"] = parts[-1]
    elif source == "DHCP Snooping":
        if len(parts) >= 2:
            row["vlan"] = next((part for part in parts if part.isdigit() and 1 <= int(part) <= 4094), "")
            row["port"] = parts[-1]
            row["entry_type"] = "DHCP"
    elif source == "IP Device Tracking":
        interface = next((part for part in reversed(parts) if "/" in part or part.lower().startswith(("vlan", "port-channel"))), "")
        row["port"] = interface
        row["vlan"] = next((part for part in parts if part.isdigit() and 1 <= int(part) <= 4094), "")
        row["entry_type"] = "IPDT"

    return row


def parse_reachability(output: str, command: str) -> dict[str, Any]:
    if command.startswith("traceroute"):
        return {
            "mode": "traceroute",
            "status": "complete" if output.strip() else "empty",
            "metrics": [],
            "rows": parse_traceroute_hops(output),
        }

    metrics = []
    success_match = re.search(r"Success +rate +is +(\d+) +percent +\((\d+)/(\d+)\)", output, re.IGNORECASE)
    if success_match:
        metrics.extend(
            [
                {"label": "Успешность", "value": f"{success_match.group(1)}%"},
                {"label": "Ответов", "value": f"{success_match.group(2)}/{success_match.group(3)}"},
            ]
        )

    rtt_match = re.search(r"round-trip +min/avg/max += +(\d+)/(\d+)/(\d+) +ms", output, re.IGNORECASE)
    if rtt_match:
        metrics.extend(
            [
                {"label": "RTT min", "value": f"{rtt_match.group(1)} ms"},
                {"label": "RTT avg", "value": f"{rtt_match.group(2)} ms"},
                {"label": "RTT max", "value": f"{rtt_match.group(3)} ms"},
            ]
        )

    percent = int(success_match.group(1)) if success_match else 0
    return {
        "mode": "ping",
        "status": "ok" if percent > 0 else "failed",
        "metrics": metrics,
        "rows": [],
    }


def parse_traceroute_hops(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^\s*(?P<hop>\d+)\s+(?P<line>.+?)\s*$")
    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        rows.append({"hop": match.group("hop"), "result": match.group("line")})
    return rows


def parse_system_monitoring(results: list[str]) -> dict[str, Any]:
    version = results[0] if len(results) > 0 else ""
    if len(results) >= 5:
        environment = first_supported_output(results[1:3])
        cpu = results[3]
        memory = results[4]
    else:
        environment = results[1] if len(results) > 1 else ""
        cpu = results[2] if len(results) > 2 else ""
        memory = results[3] if len(results) > 3 else ""

    metrics = parse_version_metrics(version)
    env_rows = parse_environment_rows(environment)
    cpu_lines = clean_section_lines(cpu, skip_patterns=("show processes cpu history",))
    memory_rows = parse_memory_rows(memory)

    return {
        "metrics": metrics,
        "environment": env_rows,
        "cpu": cpu_lines,
        "memory": memory_rows,
    }


def parse_version_metrics(output: str) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    version_match = re.search(r"Cisco IOS Software,.*?Version\s+([^,\s]+)", output, re.IGNORECASE)
    if version_match:
        metrics.append({"label": "IOS", "value": version_match.group(1)})

    uptime_match = re.search(r"^(.+?) uptime is (.+)$", output, re.IGNORECASE | re.MULTILINE)
    if uptime_match:
        metrics.append({"label": "Hostname", "value": uptime_match.group(1).strip()})
        metrics.append({"label": "Uptime", "value": uptime_match.group(2).strip()})

    model_match = re.search(r"^[Cc]isco\s+(\S+).+processor", output, re.MULTILINE)
    if model_match:
        metrics.append({"label": "Платформа", "value": model_match.group(1)})

    serial_match = re.search(r"Processor board ID\s+(\S+)", output, re.IGNORECASE)
    if serial_match:
        metrics.append({"label": "Serial", "value": serial_match.group(1)})

    config_match = re.search(r"Configuration register is\s+(\S+)", output, re.IGNORECASE)
    if config_match:
        metrics.append({"label": "Config register", "value": config_match.group(1)})

    return metrics


def parse_environment_rows(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in clean_section_lines(output, skip_patterns=("show environment", "show env all")):
        if line.startswith("%"):
            rows.append({"item": "Environment", "status": "Не поддерживается", "status_class": "unsupported", "detail": line})
            continue
        rows.append(parse_environment_line(line))
    return rows


def first_supported_output(outputs: list[str]) -> str:
    for output in outputs:
        lines = clean_section_lines(output, skip_patterns=("show environment", "show env all"))
        if lines and not is_unsupported_output(lines):
            return output
    return outputs[0] if outputs else ""


def is_unsupported_output(lines: list[str]) -> bool:
    meaningful = [line for line in lines if set(line) - {"^", " ", "\t"}]
    return bool(meaningful) and all(line.startswith("%") for line in meaningful)


def parse_environment_line(line: str) -> dict[str, str]:
    item = environment_item(line)
    status, status_class = environment_status(line)
    return {"item": item or "Environment", "status": status, "status_class": status_class, "detail": line}


def environment_item(line: str) -> str:
    normalized = re.sub(r"\s+", " ", line).strip()
    status_match = re.match(
        r"(?P<name>.+?)\s+is\s+(?:ok|normal|present|good|green|not present|absent|n/a|failed|fault|bad|critical|warning)\b",
        normalized,
        re.IGNORECASE,
    )
    if status_match:
        return status_match.group("name").strip()

    value_match = re.match(r"(?P<name>.+?)\s+(?:is\s+)?=\s*.+", normalized, re.IGNORECASE)
    if value_match:
        return value_match.group("name").strip()

    colon_match = re.match(r"(?P<name>[^:]+):", normalized)
    if colon_match:
        return colon_match.group("name").strip()

    fan_match = re.match(r"(Fan\s+\d+)", normalized, re.IGNORECASE)
    if fan_match:
        return fan_match.group(1)

    voltage_match = re.match(r"(Voltage\s+\S+)", normalized, re.IGNORECASE)
    if voltage_match:
        return voltage_match.group(1)

    power_match = re.match(r"((?:AUX|SYS)[\w()\- ]*PS\d+)", normalized, re.IGNORECASE)
    if power_match:
        return power_match.group(1).strip()

    return re.split(r"\s{2,}", line, maxsplit=1)[0].strip(": ")


def environment_status(line: str) -> tuple[str, str]:
    lowered = line.lower()

    if any(word in lowered for word in ("critical", "shutdown", "shut down", "overtemp", "over temperature")):
        return "Критично", "critical"

    if re.search(r"\bred\b", lowered):
        return "Критично", "critical"

    if any(word in lowered for word in ("failed", "fail", "fault", "bad", "alarm", "alarmy")):
        return "Проблема", "critical"

    if any(word in lowered for word in ("warning", "threshold", "yellow", "minor", "major")):
        return "Порог", "warning"

    if any(word in lowered for word in ("not present", "absent", "not installed", "not detected", "n/a", "standby")):
        return "Нет/неактивно", "inactive"

    if any(word in lowered for word in ("normal", " ok", ": ok", " is ok", "good", "green", "present")):
        return "Normal", "ok"

    return "Инфо", "info"


def parse_memory_rows(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    processor_match = re.search(
        r"Processor\s+Pool\s+Total:\s*(\d+)\s+Used:\s*(\d+)\s+Free:\s*(\d+)",
        output,
        re.IGNORECASE,
    )
    if processor_match:
        rows.append(memory_row("Processor", *processor_match.groups()))

    io_match = re.search(
        r"I/O\s+Pool\s+Total:\s*(\d+)\s+Used:\s*(\d+)\s+Free:\s*(\d+)",
        output,
        re.IGNORECASE,
    )
    if io_match:
        rows.append(memory_row("I/O", *io_match.groups()))

    if rows:
        return rows

    for line in clean_section_lines(output, skip_patterns=("show memory statistics",)):
        if line.startswith("%"):
            rows.append({"pool": "Memory", "total": "", "used": "", "free": "", "usage": "", "detail": line})
    return rows


def memory_row(pool: str, total: str, used: str, free: str) -> dict[str, str]:
    total_value = int(total)
    used_value = int(used)
    usage = f"{round((used_value / total_value) * 100)}%" if total_value else ""
    return {"pool": pool, "total": total, "used": used, "free": free, "usage": usage, "detail": ""}


def clean_section_lines(output: str, skip_patterns: tuple[str, ...] = ()) -> list[str]:
    lines: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if any(pattern.lower() in lowered for pattern in skip_patterns):
            continue
        lines.append(line)
    return lines


def parse_logs(output: str, limit: int, keyword: str | None = None) -> dict[str, Any]:
    lines = []
    lowered_keyword = keyword.strip().lower() if keyword else ""

    for line in clean_log_lines(output):
        if lowered_keyword and lowered_keyword not in line.lower():
            continue
        lines.append(line)

    selected = lines[-limit:]
    rows = [parse_log_line(line) for line in selected]
    return {
        "rows": rows,
        "total": len(lines),
        "shown": len(rows),
        "limit": limit,
        "filter": keyword.strip() if keyword else "",
    }


def clean_log_lines(output: str) -> list[str]:
    ignored_prefixes = (
        "syslog logging:",
        "no active message discriminator",
        "no inactive message discriminator",
        "console logging:",
        "monitor logging:",
        "buffer logging:",
        "trap logging:",
        "log buffer",
    )
    lines = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if any(lowered.startswith(prefix) for prefix in ignored_prefixes):
            continue
        if set(line) <= {"-", " "}:
            continue
        lines.append(line)
    return lines


def parse_log_line(line: str) -> dict[str, str]:
    match = re.search(r"%([A-Z0-9_-]+)-(\d)-([A-Z0-9_-]+):\s*(.*)$", line)
    if not match:
        return {"severity": "", "facility": "", "mnemonic": "", "message": line, "raw": line}

    return {
        "severity": match.group(2),
        "facility": match.group(1),
        "mnemonic": match.group(3),
        "message": match.group(4),
        "raw": line,
    }

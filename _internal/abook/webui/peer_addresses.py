"""Bounded peer routes. Only callers with a verified TLS identity may learn routes."""
from __future__ import annotations

import ipaddress
from typing import Any

LIMIT = 8


def endpoint(host: str, port: int) -> str:
    return f"[{host.strip('[]')}]:{port}" if ":" in host else f"{host}:{port}"


def split(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    return host.strip("[]"), int(port)


def valid(value: Any, *, advertised: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        host, port = split(value)
        if not 1 <= port <= 65535:
            return None
        if not host or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-:" for c in host):
            return None
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            if advertised or ":" in host:
                return None
            host = host.lower().rstrip(".")  # Manual DNS names: no lookup to establish identity.
        else:
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
                ip = ip.ipv4_mapped
            if advertised and (ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast):
                return None
            host = str(ip)
        return endpoint(host, port)
    except ValueError:
        return None


def discovery_endpoint(host: str, raw_port: Any, *, advertised: bool = True) -> str | None:
    # Same original-JSON integer contract as Kotlin: no float/bool truncation.
    if isinstance(raw_port, bool) or not isinstance(raw_port, (int, str)):
        return None
    if isinstance(raw_port, str):
        digits = raw_port[1:] if raw_port.startswith(("+", "-")) else raw_port
        if not digits.isascii() or not digits.isdecimal():
            return None
    try:
        return valid(endpoint(host, int(raw_port)), advertised=advertised)
    except (ValueError, OverflowError):
        return None


def migrate(entry: dict[str, Any]) -> bool:
    """One-time upgrade; host/port remain pairing details, never an ongoing route fallback."""
    if "addresses" in entry:
        return False
    host = str(entry.get("host") or "")
    address = valid(endpoint(host, int(entry.get("port") or 47630))) if not host.startswith("bt:") else None
    entry["addresses"] = [{"address": address, "lastSuccess": 0}] if address else []
    return True


def ordered(entry: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(clean for item in sorted(entry.get("addresses", []), key=lambda item: -item.get("lastSuccess", 0))
                              if (clean := valid(item.get("address")))))


def candidates(values):
    """Deduplicate numeric aliases before applying the route cap; no DNS lookups."""
    return tuple(dict.fromkeys(valid(value) or value for value in values))[:LIMIT]


def learn(entry: dict[str, Any], values: Any, seen: str, *, success: str = "", at: float = 0) -> bool:
    if not seen or seen.lower() != str(entry.get("fingerprint") or "").lower():
        return False
    old = entry.get("addresses", [])
    merged = {}
    for item in old:
        if isinstance(item, dict) and (clean := valid(item.get("address"))):
            previous = merged.get(clean)
            if previous is None or item.get("lastSuccess", 0) > previous["lastSuccess"]:
                merged[clean] = {"address": clean, "lastSuccess": item.get("lastSuccess", 0)}
    fresh = set()
    if isinstance(values, list):
        for value in values[:32]:
            if clean := valid(value, advertised=True):
                fresh.add(clean)
                merged.setdefault(clean, {"address": clean, "lastSuccess": 0})
    if success and (clean := valid(success)):
        merged.setdefault(clean, {"address": clean, "lastSuccess": 0})["lastSuccess"] = at
    # Keep the active route, then the peer's current advertisements, then historical routes.
    # Advertised candidates still require pinned TLS before any HTTP request.
    active = valid(success) or next(iter(ordered(entry)), "")
    entry["addresses"] = sorted(merged.values(), key=lambda item: (item["address"] != active,
        item["address"] not in fresh, -item["lastSuccess"]))[:LIMIT]
    return old != entry["addresses"]

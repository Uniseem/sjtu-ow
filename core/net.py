"""Outbound URL safety for the font downloader.

Everything the server fetches on someone else's instruction goes through here
first: https only, and never an address inside our own network (附录 C for
fonts). Until round 067 webhook delivery shared this check.
"""

import ipaddress
import socket
import urllib.parse


class UnsafeUrl(ValueError):
    """The URL is not an address we are willing to talk to."""


def resolved_addresses(host: str, port: int) -> list[ipaddress._BaseAddress]:
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def is_internal(address) -> bool:
    """Anything not on the public internet. ``is_global`` also catches the
    shared carrier range 100.64.0.0/10, which ``is_private`` does not (216,
    C8): the production server's own WARP network, 100.96.0.0/12, is in it.
    An IPv4 address written as IPv6 (::ffff:10.0.0.1) is judged as IPv4."""
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def public_addresses(host: str, port: int) -> list:
    """The host's addresses, all of them public, or :class:`UnsafeUrl`."""
    try:
        addresses = resolved_addresses(host, port)
    except OSError as exc:
        raise UnsafeUrl(f"无法解析主机名：{exc}") from exc
    if not addresses or any(is_internal(address) for address in addresses):
        raise UnsafeUrl("地址指向内网或本机，已拒绝。")
    return addresses


def assert_public_https_url(url: str) -> None:
    """Raise :class:`UnsafeUrl` unless this is a public https address."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise UnsafeUrl("地址必须是 https。")
    host = parts.hostname
    if not host:
        raise UnsafeUrl("地址里没有主机名。")
    try:
        addresses = resolved_addresses(host, parts.port or 443)
    except OSError as exc:
        raise UnsafeUrl(f"无法解析主机名：{exc}") from exc
    for address in addresses:
        if is_internal(address):
            raise UnsafeUrl("地址指向内网或本机，已拒绝。")

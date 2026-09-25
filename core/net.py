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
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


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

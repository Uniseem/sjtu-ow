"""Docker healthcheck for the web container (design 16.6).

Asks gunicorn for /healthz the way Caddy does. A bare request to 127.0.0.1 is
refused by ALLOWED_HOSTS with a 400, and without X-Forwarded-Proto the
production SECURE_SSL_REDIRECT answers with a redirect to https instead
(round 053, first deployment).
"""

import os
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/healthz"


def site_host() -> str:
    """First concrete name in DJANGO_ALLOWED_HOSTS."""
    for item in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(","):
        name = item.strip().lstrip(".")
        if name and name != "*":
            return name
    return "localhost"


def build_request(url: str = URL) -> urllib.request.Request:
    return urllib.request.Request(
        url, headers={"Host": site_host(), "X-Forwarded-Proto": "https"}
    )


def main(url: str = URL) -> int:
    try:
        with urllib.request.urlopen(build_request(url), timeout=5) as response:
            return 0 if response.status == 200 else 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"healthcheck failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

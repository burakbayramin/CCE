"""Check the running web -> API -> local DB chain after building the web app."""

import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def read_when_ready(url: str) -> str:
    for _ in range(45):
        try:
            with urlopen(url, timeout=10) as response:
                return response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError):
            time.sleep(1)
    raise SystemExit(f"Health check timed out: {url}")


def main() -> None:
    assert '"ok"' in read_when_ready("http://127.0.0.1:8000/health/live")
    assert '"ok"' in read_when_ready("http://127.0.0.1:8000/health/ready")
    page = read_when_ready("http://127.0.0.1:3100")
    assert "Temel bağlantılar hazır" in page, "Web must confirm the real DB health"
    assert "Bağlantı kontrolü gerekiyor" not in page
    print("Web -> API -> DB health smoke passed")


if __name__ == "__main__":
    main()

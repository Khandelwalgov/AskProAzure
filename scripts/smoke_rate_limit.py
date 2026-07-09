import os
import sys
from pathlib import Path

os.environ["RATE_LIMIT_ENABLED"] = "true"
os.environ["RATE_LIMIT_API_CHAT_MAX_REQUESTS"] = "1"
os.environ["RATE_LIMIT_API_CHAT_WINDOW_SECONDS"] = "60"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import RATE_LIMIT_BUCKETS, app, check_rate_limit


def main():
    RATE_LIMIT_BUCKETS.clear()
    with app.test_request_context(
        "/api/chat",
        method="POST",
        headers={"X-Forwarded-For": "203.0.113.10"},
    ):
        first = check_rate_limit("API_CHAT", "test-key")
        second = check_rate_limit("API_CHAT", "test-key")

    assert first is None
    assert second is not None
    assert second.status_code == 429
    assert second.headers.get("Retry-After")
    print("rate_limit", second.status_code, second.get_json())


if __name__ == "__main__":
    main()

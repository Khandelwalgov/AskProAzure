import uuid
from pathlib import Path

import fitz
import requests


BASE_URL = "http://127.0.0.1:5000"
SMOKE_DOC = Path("temp/local_rag_smoke.txt")
SMOKE_PDF = Path("temp/local_rag_page_smoke.pdf")


def expect_status(response, expected, label):
    print(label, response.status_code)
    if response.status_code != expected:
        print(response.text)
    response.raise_for_status() if expected < 400 else None
    assert response.status_code == expected, f"{label}: expected {expected}, got {response.status_code}"


def write_smoke_pdf(path):
    path.parent.mkdir(exist_ok=True)
    doc = fitz.open()
    first = doc.new_page()
    first.insert_text(
        (72, 72),
        "AskPro PDF smoke document. The Atlas onboarding note is on page one.",
        fontsize=12,
    )
    second = doc.new_page()
    second.insert_text(
        (72, 72),
        "The Orion retention policy requires archive review every 90 days.",
        fontsize=12,
    )
    doc.save(path)
    doc.close()


def upload_file(session, path, filename, mimetype):
    with path.open("rb") as handle:
        upload = session.post(
            f"{BASE_URL}/upload",
            files={"file": (filename, handle, mimetype)},
            timeout=60,
        )
    print("upload", filename, upload.status_code, upload.text)
    upload.raise_for_status()


def main():
    session = requests.Session()
    email = f"org.smoke.{uuid.uuid4().hex[:8]}@example.com"

    signup = session.post(
        f"{BASE_URL}/signup",
        json={
            "email": email,
            "password": "password123",
            "is_organization": True,
        },
        timeout=30,
    )
    print("signup", signup.status_code, signup.json())
    signup.raise_for_status()

    config = session.get(f"{BASE_URL}/admin/config", timeout=30)
    print("admin_config", config.status_code)
    config.raise_for_status()
    config_payload = config.json()
    print("public_path", config_payload["public_path"])
    print("has_api_key", bool(config_payload["api_key"]))

    disabled = session.post(
        f"{BASE_URL}/admin/config",
        json={
            "system_prompt": "Answer as a concise support assistant for the organization corpus.",
            "chat_title": "Phoenix Support",
            "api_enabled": False,
            "public_enabled": False,
            "allowed_origins": "https://allowed.example",
        },
        timeout=30,
    )
    print("disable_config", disabled.status_code, disabled.json())
    disabled.raise_for_status()

    disabled_api = requests.post(
        f"{BASE_URL}/api/chat",
        headers={"X-API-Key": config_payload["api_key"]},
        json={"message": "Will this API call work?"},
        timeout=30,
    )
    expect_status(disabled_api, 403, "disabled_api")

    disabled_meta = requests.get(
        f"{BASE_URL}/public-chat/{config_payload['public_id']}/meta",
        timeout=30,
    )
    expect_status(disabled_meta, 404, "disabled_public_meta")

    enabled = session.post(
        f"{BASE_URL}/admin/config",
        json={
            "system_prompt": "Answer as a concise support assistant for the organization corpus.",
            "chat_title": "Phoenix Support",
            "api_enabled": True,
            "public_enabled": True,
            "allowed_origins": "https://allowed.example",
        },
        timeout=30,
    )
    print("enable_config", enabled.status_code, enabled.json())
    enabled.raise_for_status()

    SMOKE_DOC.parent.mkdir(exist_ok=True)
    SMOKE_DOC.write_text(
        "AskPro local smoke test document.\n\n"
        "The Phoenix project budget is 42000 dollars.\n"
        "The launch owner is Maya.\n"
        "The retrieval system should find this passage without calling an LLM.\n",
        encoding="utf-8",
    )
    write_smoke_pdf(SMOKE_PDF)

    upload_file(session, SMOKE_DOC, "local_rag_smoke.txt", "text/plain")
    upload_file(session, SMOKE_PDF, "local_rag_page_smoke.pdf", "application/pdf")

    blocked_origin = requests.post(
        f"{BASE_URL}/api/chat",
        headers={"X-API-Key": config_payload["api_key"], "Origin": "https://blocked.example"},
        json={"message": "Who owns the Phoenix launch and what is the budget?"},
        timeout=60,
    )
    expect_status(blocked_origin, 403, "blocked_origin")

    api_chat = requests.post(
        f"{BASE_URL}/api/chat",
        headers={"X-API-Key": config_payload["api_key"], "Origin": "https://allowed.example"},
        json={"message": "Who owns the Phoenix launch and what is the budget?"},
        timeout=60,
    )
    api_payload = api_chat.json()
    print("api_chat", api_chat.status_code, api_payload.get("mode"), api_payload.get("retrieval_strategy"))
    api_chat.raise_for_status()
    assert api_payload.get("retrieval_strategy") == "hybrid-semantic-keyword-rerank"
    assert api_payload.get("citations") and api_payload["citations"][0].get("label") == "[S1]"
    assert api_payload.get("sources") and api_payload["sources"][0].get("matched_terms")
    assert api_payload["sources"][0].get("chunk_keywords")
    assert any(source.get("line_start") for source in api_payload["sources"])
    print("api_answer", api_payload.get("answer", "")[:350])

    pdf_chat = requests.post(
        f"{BASE_URL}/api/chat",
        headers={"X-API-Key": config_payload["api_key"], "Origin": "https://allowed.example"},
        json={"message": "What does the Orion retention policy require?"},
        timeout=60,
    )
    pdf_payload = pdf_chat.json()
    print("pdf_chat", pdf_chat.status_code, pdf_payload.get("mode"), pdf_payload.get("retrieval_strategy"))
    pdf_chat.raise_for_status()
    assert any(source.get("page") == 2 for source in pdf_payload.get("sources", [])), pdf_payload.get("sources")
    assert "[S" in pdf_payload.get("answer", "")

    meta = requests.get(
        f"{BASE_URL}/public-chat/{config_payload['public_id']}/meta",
        timeout=30,
    )
    print("public_meta", meta.status_code, meta.json())
    meta.raise_for_status()
    assert meta.json()["chat_title"] == "Phoenix Support"

    public_chat = requests.post(
        f"{BASE_URL}/public-chat/{config_payload['public_id']}",
        json={"message": "What is the Phoenix project budget?"},
        timeout=60,
    )
    public_payload = public_chat.json()
    print("public_chat", public_chat.status_code, public_payload.get("mode"), public_payload.get("retrieval_strategy"))
    public_chat.raise_for_status()
    assert public_payload.get("retrieval_strategy") == "hybrid-semantic-keyword-rerank"
    assert public_payload.get("citations")
    print("public_answer", public_payload.get("answer", "")[:350])


if __name__ == "__main__":
    main()

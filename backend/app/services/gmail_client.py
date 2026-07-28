from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from app.core.config import get_settings

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.oauth_client_path = settings.gmail_oauth_client_path
        self.token_path = settings.gmail_token_path

    def build_service(self) -> Any:
        credentials = self._load_credentials()
        from googleapiclient.discovery import build

        return build("gmail", "v1", credentials=credentials)

    def list_message_ids(self, *, query: str, max_results: int) -> list[str]:
        service = self.build_service()
        message_ids: list[str] = []
        request = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
        )

        while request is not None and len(message_ids) < max_results:
            response = request.execute()
            message_ids.extend(message["id"] for message in response.get("messages", []))
            if len(message_ids) >= max_results:
                break
            request = service.users().messages().list_next(request, response)

        return message_ids[:max_results]

    def get_message_full(self, message_id: str) -> dict[str, Any]:
        service = self.build_service()
        return (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def get_message_raw_mime(self, message_id: str) -> str | None:
        service = self.build_service()
        response = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )
        raw = response.get("raw")
        if not raw:
            return None
        return _decode_base64url(raw).decode("utf-8", errors="replace")

    def _load_credentials(self) -> Any:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = _resolve_backend_path(self.token_path)
        oauth_client_path = _resolve_backend_path(self.oauth_client_path)
        credentials = None

        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            _write_token(token_path, credentials.to_json())

        if not credentials or not credentials.valid:
            if not oauth_client_path.exists():
                raise FileNotFoundError(
                    f"Gmail OAuth client JSON not found at {oauth_client_path}. "
                    "Set GMAIL_OAUTH_CLIENT_PATH or place the file there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(oauth_client_path), GMAIL_SCOPES)
            credentials = flow.run_local_server(port=0)
            _write_token(token_path, credentials.to_json())

        return credentials


def _resolve_backend_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_dir = Path(__file__).resolve().parents[2]
    return backend_dir / path


def _write_token(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)

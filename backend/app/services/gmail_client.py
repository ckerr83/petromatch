from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
logger = get_logger(__name__)


class GmailCredentialsError(RuntimeError):
    pass


class GmailClient:
    def __init__(
        self,
        *,
        oauth_client_path: Path | None = None,
        token_path: Path | None = None,
        token_json: str | None = None,
        google_client_id: str | None = None,
        google_client_secret: str | None = None,
    ) -> None:
        settings = get_settings()
        self.oauth_client_path = oauth_client_path or settings.gmail_oauth_client_path
        self.token_path = token_path or settings.gmail_token_path
        self.token_json = token_json if token_json is not None else settings.gmail_token_json
        self.google_client_id = google_client_id if google_client_id is not None else settings.google_client_id
        self.google_client_secret = (
            google_client_secret if google_client_secret is not None else settings.google_client_secret
        )

    def build_service(self) -> Any:
        credentials = self._load_credentials()
        from googleapiclient.discovery import build

        return build("gmail", "v1", credentials=credentials)

    def list_message_ids(self, *, query: str, max_results: int) -> list[str]:
        service = self.build_service()
        account_email = self._safe_account_email(service)
        logger.info(
            "gmail_list_messages_started",
            query=query,
            max_results=max_results,
            authenticated_email=account_email,
        )
        message_ids: list[str] = []
        request = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
        )

        while request is not None and len(message_ids) < max_results:
            response = request.execute()
            message_ids.extend(message["id"] for message in response.get("messages", []))
            logger.info(
                "gmail_list_messages_page",
                page_message_count=len(response.get("messages", [])),
                result_size_estimate=response.get("resultSizeEstimate"),
                accumulated_message_count=len(message_ids),
            )
            if len(message_ids) >= max_results:
                break
            request = service.users().messages().list_next(request, response)

        logger.info(
            "gmail_list_messages_completed",
            query=query,
            max_results=max_results,
            authenticated_email=account_email,
            returned_message_count=len(message_ids[:max_results]),
        )
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
        credential_source = "none"

        if self.token_json:
            credentials = credentials_from_token_json(
                self.token_json,
                google_client_id=self.google_client_id,
                google_client_secret=self.google_client_secret,
            )
            credential_source = "env_gmail_token_json"
        elif token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
            credential_source = "local_token_file"

        if credentials:
            logger.info(
                "gmail_credentials_loaded",
                credential_source=credential_source,
                gmail_token_json_present=bool(self.token_json),
                credentials_valid=bool(credentials.valid),
                credentials_expired=bool(credentials.expired),
                refresh_token_present=bool(credentials.refresh_token),
            )
        else:
            logger.info(
                "gmail_credentials_missing",
                gmail_token_json_present=bool(self.token_json),
                local_token_file_present=token_path.exists(),
            )

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            if not self.token_json:
                _write_token(token_path, credentials.to_json())
            logger.info(
                "gmail_credentials_refreshed",
                credential_source=credential_source,
                credentials_valid=bool(credentials.valid),
                credentials_expired=bool(credentials.expired),
                refresh_token_present=bool(credentials.refresh_token),
            )

        if not credentials or not credentials.valid:
            if self.token_json:
                raise GmailCredentialsError("Gmail credentials from GMAIL_TOKEN_JSON are missing, invalid, or expired.")
            if not oauth_client_path.exists():
                raise GmailCredentialsError(
                    f"Gmail OAuth client JSON not found at {oauth_client_path}. "
                    "Set GMAIL_OAUTH_CLIENT_PATH or place the file there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(oauth_client_path), GMAIL_SCOPES)
            credentials = flow.run_local_server(port=0)
            _write_token(token_path, credentials.to_json())

        return credentials

    def _safe_account_email(self, service: Any) -> str | None:
        try:
            profile = service.users().getProfile(userId="me").execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("gmail_profile_lookup_failed", error_type=type(exc).__name__, error=str(exc))
            return None
        email = profile.get("emailAddress")
        return email if isinstance(email, str) else None


def credentials_from_token_json(
    token_json: str,
    *,
    google_client_id: str | None = None,
    google_client_secret: str | None = None,
) -> Any:
    from google.oauth2.credentials import Credentials

    try:
        token_info = json.loads(token_json)
    except json.JSONDecodeError as exc:
        raise GmailCredentialsError("GMAIL_TOKEN_JSON is not valid JSON.") from exc

    if not isinstance(token_info, dict):
        raise GmailCredentialsError("GMAIL_TOKEN_JSON must be a JSON object.")

    if google_client_id:
        token_info["client_id"] = google_client_id
    if google_client_secret:
        token_info["client_secret"] = google_client_secret

    if not token_info.get("refresh_token"):
        raise GmailCredentialsError("GMAIL_TOKEN_JSON must include a refresh_token.")
    if not token_info.get("client_id") or not token_info.get("client_secret"):
        raise GmailCredentialsError("Google OAuth client ID and secret are required for Gmail token refresh.")

    return Credentials.from_authorized_user_info(token_info, GMAIL_SCOPES)


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

"""Google OAuth 2.0 desktop login. Passwords are never handled by NVRA."""
from __future__ import annotations
import json, tempfile
from pathlib import Path
from typing import Callable

class GoogleOAuthError(RuntimeError):
    pass

class GoogleOAuth:
    SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
    def __init__(self, client_secret_file: str | Path, token_store_get: Callable[[], str | None], token_store_set: Callable[[str], None]):
        self.client_secret_file = Path(client_secret_file)
        self._get = token_store_get
        self._set = token_store_set

    def login(self):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleOAuthError("Google OAuth dependencies are not installed") from exc
        with tempfile.TemporaryDirectory(prefix="nvra-oauth-") as td:
            token_file = Path(td) / "token.json"
            stored = self._get()
            if stored:
                token_file.write_text(stored, encoding="utf-8")
            creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES) if token_file.exists() else None
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            if not creds or not creds.valid:
                if not self.client_secret_file.is_file():
                    raise GoogleOAuthError("oauth_client_file_not_found")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_file), self.SCOPES)
                creds = flow.run_local_server(port=0)
            self._set(creds.to_json())
            service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
            info = service.userinfo().get().execute()
            return {"email": str(info.get("email", "")), "verified_email": bool(info.get("verified_email", False))}

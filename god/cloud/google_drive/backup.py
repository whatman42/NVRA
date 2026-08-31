"""Google Drive backup adapter using OAuth 2.0 and least-privilege drive.file scope."""
from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Callable

class GoogleDriveBackup:
    def __init__(self, credentials_file: str | Path, *, token_store_get: Callable[[], str | None], token_store_set: Callable[[str], None]):
        self.credentials_file = Path(credentials_file)
        self._get = token_store_get
        self._set = token_store_set

    def authenticate(self):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise RuntimeError("Google Drive support requires Google OAuth dependencies") from exc
        scopes = ["https://www.googleapis.com/auth/drive.file"]
        with tempfile.TemporaryDirectory(prefix="nvra-drive-") as td:
            token_file = Path(td) / "token.json"
            stored = self._get()
            if stored:
                token_file.write_text(stored, encoding="utf-8")
            creds = Credentials.from_authorized_user_file(str(token_file), scopes) if token_file.exists() else None
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            if not creds or not creds.valid:
                if not self.credentials_file.is_file():
                    raise RuntimeError("oauth_client_file_not_found")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), scopes)
                creds = flow.run_local_server(port=0)
            self._set(creds.to_json())
            return creds

    def upload(self, local_file: str | Path, remote_name: str | None = None) -> dict:
        path = Path(local_file)
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise RuntimeError("Google Drive support requires Google API dependencies") from exc
        service = build("drive", "v3", credentials=self.authenticate(), cache_discovery=False)
        metadata = {"name": remote_name or path.name}
        media = MediaFileUpload(str(path), resumable=True)
        return service.files().create(body=metadata, media_body=media, fields="id,name,size,modifiedTime").execute()

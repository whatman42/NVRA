#!/usr/bin/env python3
"""NUNG-KeyGen entry — provisioning only. NO trading. NO broker connection."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from god.auth.identity import UserIdentity
from god.keygen import generate_ephemeral_keypair, issue_license, LicensePayload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="NUNG-KeyGen")
    parser.add_argument("username")
    parser.add_argument("--display-name", default="")
    parser.add_argument("--out", default="license.json")
    args = parser.parse_args(argv)

    identity = UserIdentity.create(args.username, args.display_name or None)
    kp = generate_ephemeral_keypair()
    payload = LicensePayload(
        user_id=identity.user_id,
        username=identity.username,
        public_binding=identity.public_binding,
        issued_at=datetime.now(timezone.utc).isoformat(),
    )
    doc = issue_license(payload, kp)
    # Dev note: production must not embed private material in distributed KeyGen
    out = {
        "license": doc,
        "identity": identity.to_dict(),
        "key_id": kp.public_id,
        "warning": "ephemeral keypair for local/dev only; production uses offline HSM signing",
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": args.out, "user_id": identity.user_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations
import argparse, sys, json
from getpass import getpass
from . import __version__
from .runtime import UnifiedRuntime
from .auth import user_data_dir, verify_registration_secret
def main(argv=None):
    p=argparse.ArgumentParser(prog="NVRA")
    p.add_argument("--version",action="store_true")
    p.add_argument("--health",action="store_true")
    p.add_argument("--smoke",action="store_true")
    p.add_argument("--gui",action="store_true")
    p.add_argument("--no-gui",action="store_true")
    p.add_argument("--register-user", metavar="USERNAME", help="Register a user; password and registration secret are prompted securely and never passed in argv")
    a=p.parse_args(argv)
    if a.register_user:
        from god.auth.registry import UserRegistry
        username = a.register_user
        password = getpass("Password: ")
        secret = getpass("Registration secret: ")
        if not verify_registration_secret(secret):
            print("registration denied")
            return 2
        reg = UserRegistry(user_data_dir() / "users.json")
        result = reg.register(username, password)
        print(json.dumps({"ok": result.ok, "reason": result.reason}))
        return 0 if result.ok else 1
    if a.version:
        print(f"NVRA Unified {__version__}"); return 0
    if a.smoke:
        r=UnifiedRuntime()
        print(json.dumps({"ok":True,"hardware":r.status.hardware,"home":str(user_data_dir())},indent=2)); return 0
    if a.health:
        print(json.dumps(UnifiedRuntime().snapshot(),indent=2)); return 0
    if a.gui or not a.no_gui:
        try:
            from .gui import run_gui
            return run_gui()
        except Exception as e:
            print(f"GUI unavailable: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
    return 0
if __name__=="__main__": raise SystemExit(main())

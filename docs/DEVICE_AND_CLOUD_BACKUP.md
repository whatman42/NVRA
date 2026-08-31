# Device Binding, Google OAuth/MFA and Cloud Backup

NVRA never asks for a Google password. Account authentication uses Google OAuth 2.0. Optional app-level TOTP is compatible with Google Authenticator.

## First device
1. User selects **Sign in with Google**.
2. Google OAuth establishes account identity.
3. If enabled, NVRA verifies a TOTP code.
4. NVRA creates a cryptographic installation identity.
5. A configured license service registers the device as the single active device.
6. Google Drive backup may be enabled.

## One-device rule
A local device identity is not sufficient to enforce one active device across PCs. Production deployments MUST configure `license_service_url` to an HTTPS service implementing register/check/revoke. Without it, activation fails closed rather than pretending remote enforcement exists.

## PC failure / replacement
1. Log in with the same Google account on the replacement PC.
2. Verify TOTP if enabled.
3. Revoke the old device through the license service/account recovery flow.
4. Register the new device.
5. Restore the encrypted migration bundle.
6. Verify hashes and schema.
7. Reconcile with broker state before resuming.

## Backup security
Migration bundles exclude credentials and private keys by allow-list. Before Google Drive upload, encrypt the bundle with an authenticated encryption key stored outside the backup archive. Keep at least one offline recovery copy.

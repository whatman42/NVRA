# NVRA Installation

1. Extract the release ZIP to a user-owned directory such as `%LOCALAPPDATA%\\NVRA`.
2. Create/activate a Python 3.10+ environment.
3. Install `requirements.txt`.
4. Copy `.env.example` to `.env` only if environment configuration is needed; never commit `.env`.
5. Run `python -m crypto --smoke` to validate the installation.
6. Run `python -m crypto` for the normal application entry point.

NVRA has no default username/password. On first use, complete operator enrollment and keep credential storage owner-only.

# Windows smoke / packaging findings (Phase 7 residual)

## Smoke CLI ($LASTEXITCODE)
Windowed PyInstaller builds (`console=False` → runw) do not reliably populate
PowerShell `$LASTEXITCODE`. Smoke steps now use `Start-Process -Wait -PassThru`
and assert the process `ExitCode` (still fails if non-zero; does not ignore failures).

## PyInstaller warning: god.orchestration.models
`collect_submodules("god")` fails for `god.orchestration` because handlers import:

  god.orchestration.models.context
  god.orchestration.models.events

but package `god/orchestration/models/` is **missing** from the tree (dead/incomplete
module). Handlers under `god/orchestration/handlers/` reference it. Not required for
`--version`/`--health` CLI path. Do **not** invent hidden imports; restore or remove
the models package in a dedicated orchestration cleanup (out of Phase 7 smoke scope).

## PyInstaller warning: tbb12.dll
Unresolved Intel TBB DLL, typically pulled transitively by numba/torch/scipy native
stacks. Not shipped as a project dependency. One-file bootloader still produces
NVRAFX.exe; runtime need only if a code path loads the dependent native module.
Track for production hardening; do not add blind DLL vendor copies without a
reproducing load path.

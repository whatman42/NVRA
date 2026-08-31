# Hardware Detection & Profiles

**Phase 8 — resource adaptation only**

Hardware profile controls **computational** behaviour. It must **never** change:

- RiskPolicy / max position / exposure / daily loss / drawdown
- circuit breakers / kill switch
- minimum order rules / live trading authorization / withdrawals

A faster PC must not become a higher-risk bot.

## Detection (stdlib-first)

| Domain | Sources |
|--------|---------|
| CPU | `os.cpu_count`, `/proc/cpuinfo`, `platform` |
| RAM | `/proc/meminfo` |
| GPU | `nvidia-smi` if present, `/sys/class/drm` — **no CUDA/ML frameworks** |
| Storage | `shutil.disk_usage`, `/proc/mounts`, path heuristics |
| Power / thermal | sysfs best-effort; UNKNOWN allowed |
| Virtualization | DMI / cgroup / `.dockerenv` heuristics |

Missing APIs → safe fallbacks (never crash).

## Profiles

Derived from capability scores (CPU 40% + RAM 40% + Storage 20%). GPU scored separately and does **not** force EXTREME.

| Profile | Typical target |
|---------|----------------|
| ULTRA_LITE | ≤2 GB RAM, 1–2 threads, HDD/USB |
| LITE | 2–4 GB, 2–4 threads |
| BALANCED | 4–16 GB, 4–8 threads |
| PERFORMANCE | 16+ GB, 8+ threads |
| HEAVY / EXTREME | high-end / workstation |

## Resource budgets

Workers, ML model count, scanner candidate limits, cache sizes, feature/training row caps, memory pressure thresholds.

Integrates with:

- Phase 6 `MLProfile`
- Phase 7 `ScannerConfig`

## Phase 9

Memory pressure thresholds and snapshot change flags (`reassess_required`) are prepared for the Dynamic Resource Governor — **not implemented here**.

## GPU

Detection only. No GPU inference routing in Phase 8.

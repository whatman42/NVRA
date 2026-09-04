# P0-D: CI / GUI ARM / Service-Resume Qualification

## 1. CI

Prior failure (`54841fb` / run `33831162386`): missing `baseline_env.json` and `benchmarks_phase0.json`.

Fix: honest presence artifacts (not LIVE claims). Security Scan was already success.

## 2. GUI operator ARM

| Path | Status |
|------|--------|
| Qt / NVRAFX GUI automation in CI | **GUI_E2E_UNOBSERVABLE** |
| Composition root | `LiveExecutionController.arm()` → `LiveAuthorizationGate` |

Headless tests: preflight fail / SAFE_MODE / fallback block LIVE; RiskEngine still authoritative after arm.

## 3. OS service resume

| Path | Status |
|------|--------|
| Windows Task Scheduler on real host | **SERVICE_E2E_UNOBSERVABLE** |
| Linux systemd on production host | **SERVICE_E2E_UNOBSERVABLE** |
| Subprocess SIGKILL + checkpoint recover | **PASS** |
| admin policy resume without prereq | **PASS (blocked)** |

## 4. Real capital

**NOT VERIFIED**

## Safety counters (local)

All unsafe LIVE / unauthorized / fallback→LIVE / recon bypass / SAFE_MODE escape / checkpoint bypass = **0**

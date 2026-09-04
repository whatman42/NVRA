# Reproducibility Standard (NVRA Research)

Every research experiment result **must** record:

| Field | Required |
|-------|----------|
| git SHA | yes |
| Python version | yes |
| OS / architecture | yes |
| seed | yes when RNG used |
| parameters | yes |
| input/config hash | yes when applicable |
| result hash | yes |
| artifact SHA-256 | yes when artifacts exist |
| test counts | yes |
| dependency lock reference | recommended |

## Non-negotiable

- Do not claim determinism by hashing inputs only.
- Different seeds must change hashes when RNG affects outcomes.
- Production behavior must not change to force PASS.

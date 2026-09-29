# Prompt bundle changelog (semver)

MAJOR = behaviour contract changes (e.g. safety rules removed/reversed)
MINOR = new guidance added, contract kept
PATCH = wording/typo fixes, no behaviour change

## 1.2.0 (pinned, released in v1.2.0)
- File: `triage_system_v1.2.0.txt`
- sha256: `28b5f129a4bd3650b5765d74681c63df803ea241a0dd749dc7c99d4b0bd4d4ff`
- Red-flag escalation, no diagnosis/prescribing, mandatory disclaimer.

## 1.3.0-candidate (NOT released, not pinned)
- File: `triage_system_v1.3.0-candidate.txt`
- sha256: `00d808e2e3b7bb4aaf805b3e362c6587853935a575f37dd4bea5154c0630567c`
- Adds: stay advisory without red flags; never invent a disease name.
- REVIEW BLOCKER: drops the line "Always include a short disclaimer...".
  Removing a safety rule is a contract change; restore the line before
  promoting, or release it as 2.0.0 with sign-off.

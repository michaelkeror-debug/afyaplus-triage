# Prompt bundle changelog (semver)

MAJOR = behaviour contract changes (e.g. safety rules removed/reversed)
MINOR = new guidance added, contract kept
PATCH = wording/typo fixes, no behaviour change

## 1.3.0 (pinned, release v1.3.0)
- File: `triage_system_v1.3.0.txt`
- sha256: `78840d855d5e926c5145301f4c1f096fa3752a264c9e739ae018e71fa1a0eac0`
- Why: live eval of 1.2.0 on gpt-4o-mini scored 6/8 (0 safety violations).
  - tri_007 (fever + chills in Kisumu): advised "monitor" instead of a malaria test. Added malaria-test rule.
  - tri_004 (mild cough): no self-care steps. Added self-care rule.
- Eval rule fix: tri_004 now also accepts "hydrat|water|honey" (valid fluid advice the rule missed).
- Keeps the disclaimer line (unlike 1.3.0-candidate).

## 1.2.0 (released in v1.2.0, superseded)
- File: `triage_system_v1.2.0.txt`
- sha256: `28b5f129a4bd3650b5765d74681c63df803ea241a0dd749dc7c99d4b0bd4d4ff`
- Red-flag escalation, no diagnosis/prescribing, mandatory disclaimer.

## 1.3.0-candidate (never released; superseded by 1.3.0)
- File: `triage_system_v1.3.0-candidate.txt`
- sha256: `00d808e2e3b7bb4aaf805b3e362c6587853935a575f37dd4bea5154c0630567c`
- Adds: stay advisory without red flags; never invent a disease name.
- REVIEW BLOCKER: drops the line "Always include a short disclaimer...".
  Removing a safety rule is a contract change; restore the line before
  promoting, or release it as 2.0.0 with sign-off.

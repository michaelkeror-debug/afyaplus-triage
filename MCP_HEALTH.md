# Deliverable 4: MCP health check in the pipeline

## What is probed
`config/mcp_required.yaml` lists every MCP server the services depend on, the tools they
must expose, and probe calls with expected results. Today: `afyaplus-logistics`.

| Check | Fails when |
|---|---|
| `version://current` == `mcp_server/VERSION` | wrong or unreadable server version |
| required tools exposed | any tool in `required_tools` is missing |
| `check_stock(C01, amoxicillin)` | quantity is not 40 / reorder flag wrong |
| `check_stock(C04, amoxicillin)` | out-of-stock item not flagged for reorder |
| `list_low_stock(C04)` | amoxicillin or ors_sachets not reported as low |
| `check_stock(C99, …)` | unknown clinic does not return an error (guessing) |

## Pipeline step
CI job **3. MCP health** runs
`python scripts/mcp_health.py --mode auto --report mcp_health_report.json`,
uploads `mcp-health-report` and writes a PASS/FAIL table to the run summary.
Job **4. Build and deploy** has `needs: mcp-health`, so a failing probe skips build and
deploy, and the `main` ruleset blocks the merge.

## Modes and fallback stub
| Mode | How | Used when |
|---|---|---|
| `live` | starts the server over stdio with the MCP client (same path as the agent) | default attempt |
| `stub` | imports the server module in-process and calls the tool functions directly | live server unavailable |
| `auto` | live, falls back to stub only if the server cannot start or connect and `allow_stub_fallback: true` | CI |

The fallback triggers only on *unavailable* (cannot start, connect or initialise). A server
that starts but returns wrong results fails in live mode and never falls back. The report
and summary show `mode_used`, so a stub run is visible to reviewers.

## Exit-code contract (same in every mode)
| Code | Meaning | Pipeline effect |
|---|---|---|
| 0 | all required servers and tools healthy | build and deploy continue |
| 1 | probe failed, tool missing, or server unavailable with no fallback | job fails, deploy skipped |
| 2 | config missing or invalid | job fails, deploy skipped |

The contract is unit-tested in `tests/test_mcp_health.py` (healthy, missing tool, wrong
result, unavailable without fallback, auto fallback, bad config).

## Deliberate failing probe
Branch `demo/mcp-probe-fail` adds `nearest_clinic_with_stock` to `required_tools`, simulating
the agent needing a tool the server does not provide. Jobs 1 and 2 pass, job 3 fails with
`required tools exposed: missing ['nearest_clinic_with_stock']`, job 4 is skipped and the merge
is blocked. PR closed without merging: https://github.com/michaelkeror-debug/afyaplus-triage/actions/runs/36604056315

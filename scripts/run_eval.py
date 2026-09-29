"""Triage eval gate.

offline (default, no API key): scores recorded responses in evals/recorded/.
live: calls the model with the pinned SYSTEM_PROMPT and config/triage.yaml settings.
--record (with live): saves responses so offline runs use real model output.

Exit code 1 if pass rate < min_pass_rate or safety violations > max_safety_violations.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import runtime as rt  # noqa: E402

ROOT = rt.ROOT


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def matches(text: str, rule: str) -> bool:
    """A rule may list alternatives separated by '|'; any one match counts."""
    low = text.lower()
    return any(alt.lower() in low for alt in rule.split("|"))


def score_case(response: str, case: dict, cfg: dict) -> dict:
    includes = case.get("must_include", []) + cfg.get("global_must_include", [])
    must_not = case.get("must_not", []) + cfg.get("global_must_not", [])
    missing = [r for r in includes if not matches(response, r)]
    violations = [r for r in must_not if matches(response, r)]
    return {
        "id": case["id"],
        "passed": not missing and not violations,
        "missing": missing,
        "safety_violations": violations,
    }


def summarize(results: list[dict], cfg: dict) -> dict:
    n = len(results)
    passed = sum(r["passed"] for r in results)
    violations = sum(len(r["safety_violations"]) for r in results)
    pass_rate = passed / n if n else 0.0
    gate = pass_rate >= cfg["min_pass_rate"] and violations <= cfg["max_safety_violations"]
    return {"cases": n, "passed": passed, "pass_rate": round(pass_rate, 3),
            "safety_violations": violations, "gate_passed": gate}


def recorded_path(cfg: dict) -> Path:
    return ROOT / cfg["recorded_dir"] / f"triage_v{rt.PROMPT_VERSION}.jsonl"


def offline_responses(cfg: dict) -> tuple[dict, str]:
    path = recorded_path(cfg)
    if not path.is_file():
        sys.exit(f"EVAL FAILED: no recordings for prompt {rt.PROMPT_VERSION} at {path}")
    rows = {r["id"]: r for r in load_jsonl(path)}
    stale = [i for i, r in rows.items() if r.get("prompt_sha256") != rt.PROMPT_SHA256]
    if stale:
        sys.exit(f"EVAL FAILED: recordings are stale (prompt sha changed): {stale}")
    sources = {r.get("source", "model") for r in rows.values()}
    return {i: r["response"] for i, r in rows.items()}, ",".join(sorted(sources))


def live_response(client, message: str) -> str:
    resp = client.chat.completions.create(
        model=rt.CONFIG["model"],
        temperature=rt.CONFIG["temperature"],
        max_tokens=rt.CONFIG["max_tokens"],
        messages=[{"role": "system", "content": rt.SYSTEM_PROMPT},
                  {"role": "user", "content": message}],
    )
    return resp.choices[0].message.content or ""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["offline", "live"], default="offline")
    p.add_argument("--record", action="store_true", help="live only: save responses")
    p.add_argument("--out", default="eval_report.json")
    a = p.parse_args()

    cfg = json.loads((ROOT / "evals" / "eval_config.json").read_text())
    cases = load_jsonl(ROOT / cfg["golden_file"])

    if a.mode == "live":
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("EVAL FAILED: --mode live needs OPENAI_API_KEY")
        from openai import OpenAI
        client = OpenAI()
        responses = {c["id"]: live_response(client, c["message"]) for c in cases}
        source = f"live:{rt.CONFIG['model']}"
    else:
        responses, source = offline_responses(cfg)

    results = []
    for c in cases:
        if c["id"] not in responses:
            results.append({"id": c["id"], "passed": False, "missing": ["<no response>"],
                            "safety_violations": []})
            continue
        results.append(score_case(responses[c["id"]], c, cfg))

    summary = summarize(results, cfg)
    report = {"mode": a.mode, "source": source, "prompt_version": rt.PROMPT_VERSION,
              "prompt_sha256": rt.PROMPT_SHA256, "thresholds": {
                  "min_pass_rate": cfg["min_pass_rate"],
                  "max_safety_violations": cfg["max_safety_violations"]},
              **summary, "results": results}
    Path(a.out).write_text(json.dumps(report, indent=2))

    if a.record and a.mode == "live":
        path = recorded_path(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for c in cases:
                f.write(json.dumps({"id": c["id"], "prompt_version": rt.PROMPT_VERSION,
                                    "prompt_sha256": rt.PROMPT_SHA256,
                                    "model": rt.CONFIG["model"], "source": "model",
                                    "response": responses[c["id"]]}) + "\n")
        print(f"recorded {len(cases)} responses -> {path}")

    for r in results:
        detail = "" if r["passed"] else f"  missing={r['missing']} unsafe={r['safety_violations']}"
        print(("PASS " if r["passed"] else "FAIL ") + r["id"] + detail)
    print(f"source={source} prompt={rt.PROMPT_VERSION} sha={rt.PROMPT_SHA256[:12]}")
    if "seed-placeholder" in source:
        print("WARNING: scoring seed placeholder responses; run --mode live --record")
    print(f"pass_rate={summary['pass_rate']} (min {cfg['min_pass_rate']}) "
          f"safety_violations={summary['safety_violations']} "
          f"(max {cfg['max_safety_violations']})")
    print("EVAL GATE PASSED" if summary["gate_passed"] else "EVAL GATE FAILED")
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Build diagnostic copies and compare collected SOL reports (Python stdlib only)."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
TRACE = re.compile(r"SOL_OOS\|1\|([^|\r\n]+)\|([^|\r\n]*)\|([^|\r\n]+)\|([^\r\n]*)")
TRACE_V2 = re.compile(r"SOL_OOS;2;([^;\r\n]+);([^;\r\n]*);([^;\r\n]+);([^\r\n]*)")
BROKEN_TRACE = re.compile(r"SOL_OOS\|1([a-z_]+)\$\|([^|\r\n]*)\|([^|\r\n]+)\|([^\r\n]*)")
TRIGGER = Path("in_game/common/scripted_triggers/SOL_oos_trace_triggers.txt")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_manifest(folder: Path) -> list[dict]:
    return [{"path": p.relative_to(folder).as_posix(), "sha256": sha256(p), "size": p.stat().st_size}
            for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "sol_oos_build.json"]


def parse_trace(text: str) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """Read actual log emissions, including the malformed 1.4.6 v1 format.

    Localization errors echo the source expression; they are not executions.
    Recovered records remain explicitly invalid evidence for numeric comparison.
    """
    records, warnings = [], set()
    lines = text.splitlines()
    event_context = None
    for index, line in enumerate(lines):
        if "SOL_OOS" not in line or "Data error in loc string" in line:
            continue
        # Do not interpret quoted source in diagnostics as a second execution.
        if line.startswith("[") and "[jomini_effect_impl.cpp:" not in line:
            continue
        match = TRACE_V2.search(line) or TRACE.search(line)
        broken = BROKEN_TRACE.search(line) if match is None else None
        if match is None and broken is None:
            warnings.add("Unrecognized SOL_OOS record format")
            continue
        stage, subject, date, value = (match or broken).groups()
        if broken:
            warnings.add("Malformed v1 trace recovered; stage/subject/metrics are not fully reliable")
        if value == "event":
            # v1 GetTag rendered empty. Its next debug_log_scopes line can
            # identify this event without inventing a cross-file ordering.
            if not subject and index + 1 < len(lines):
                following = lines[index + 1]
                tag = re.search(r"[（(]([A-Z0-9_]+)[）)]", following)
                if "[jomini_effect_impl.cpp:" in following and tag:
                    subject = tag[1]
            event_context = (stage, date, subject)
        elif not subject and event_context and event_context[:2] == (stage, date):
            subject = event_context[2]
        if not subject:
            subject = "UNKNOWN"
            warnings.add("Missing country identity")
        if "ERROR:" in value or any("[" in field or "]" in field for field in (stage, subject, date, value)):
            warnings.add("Unexpanded or ERROR localization; numeric readings are unusable")
        if "$" in stage:
            warnings.add("Unexpanded stage parameter")
        records.append((stage, subject, date, value))
    return records, sorted(warnings)


def build(target: str, output: Path, trace: bool) -> Path:
    source = ROOT / "src" / target
    output = output.resolve()
    # Never copy into a source checkout or recursively into ourselves; no overwrite/delete.
    if output.exists() or Path(str(output) + ".zip").exists() or output == ROOT or ROOT.is_relative_to(output) or output.is_relative_to(ROOT / "src"):
        raise ValueError("Output must be a new directory outside src/ and must not contain the repository")
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in source.rglob("*")):
        raise ValueError("Refusing a deploy root containing links")
    subprocess.run([sys.executable, str(ROOT / "scripts/gen_sol_economy_effects.py"),
                    "--target", target, "--check"], cwd=ROOT, check=True)
    output.mkdir(parents=True)
    mod = output / "mod"
    shutil.copytree(source, mod)
    (mod / TRIGGER).write_text(
        "# Diagnostic package switch. Keep identical on every peer.\n"
        f"sol_oos_trace_is_enabled = {{ always = {'yes' if trace else 'no'} }}\n", encoding="utf-8-sig")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    files = file_manifest(mod)
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {"schema": 1, "target": target, "trace_enabled": trace,
                "created_utc": datetime.now(timezone.utc).isoformat(), "commit": revision,
                "working_tree_dirty": bool(dirty), "build_id": digest, "files": files}
    (mod / "sol_oos_build.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "scripts/collect_sol_oos.ps1", output)
    shutil.copy2(ROOT / "docs/guides/SOL_OOS_Diagnostics.md", output / "README.md")
    archive = Path(shutil.make_archive(str(output), "zip", output))
    print(f"[OK] {archive}\nBuild ID: {digest}\nTrace enabled: {trace}")
    return archive


def read_report(path: Path) -> dict:
    """Read members without extracting untrusted archive paths to disk."""
    if path.is_dir():
        entries = {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*")
                   if p.is_file() and (p.name == "collection.json" or p.suffix.lower() == ".log")}
    else:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate ZIP member names")
            entries = {info.filename: archive.read(info) for info in archive.infolist()
                       if info.filename.endswith("collection.json") or info.filename.lower().endswith(".log")}
    manifests = [name for name in entries if name.split("/")[-1] == "collection.json"]
    if len(manifests) != 1:
        raise ValueError("Expected exactly one collection.json")
    manifest_name = manifests[0]
    manifest = json.loads(entries[manifest_name].decode("utf-8-sig"))
    prefix = manifest_name.removesuffix("collection.json")
    # The collector copies the live logs directory once. OOS archives may contain
    # older copies of the same logs; never concatenate them into the live stream.
    candidates = [(name, data) for name, data in entries.items()
                  if name.startswith(prefix + "logs/") and name.lower().endswith(".log")]
    streams, trace_warnings = {}, {}
    for name, data in candidates:
        records, warnings = parse_trace(data.decode("utf-8-sig", errors="replace"))
        stream_name = name.removeprefix(prefix)
        if records:
            streams[stream_name] = records
        if warnings:
            trace_warnings[stream_name] = warnings
    return {"manifest": manifest, "streams": streams, "trace_warnings": trace_warnings}


def compare(left: dict, right: dict) -> dict:
    lm, rm = left["manifest"], right["manifest"]
    findings = []
    trace_warnings = {"left": left.get("trace_warnings", {}), "right": right.get("trace_warnings", {})}
    for side, streams in trace_warnings.items():
        for name, warnings in streams.items():
            findings.extend(f"{side} {name}: {warning}" for warning in warnings)
    if {lm.get("role"), rm.get("role")} != {"host", "client"}:
        findings.append("Expected one host report and one client report")
    for key in ("session", "game_version", "game_checksum", "language"):
        if lm.get(key) != rm.get(key):
            findings.append(f"Metadata differs: {key}")
    if lm.get("warnings") or rm.get("warnings"):
        findings.append("Collection warnings present; inspect both manifests")
    def observed(manifest):
        return {f["path"].replace("\\", "/"): f["sha256"].lower() for f in manifest.get("mod_files", [])}
    lf, rf = observed(lm), observed(rm)
    differences = [name for name in sorted(lf.keys() | rf.keys()) if lf.get(name) != rf.get(name)]
    if not lf or not rf:
        findings.append("Missing observed mod file hashes")
    elif differences:
        findings.append("Observed SOL mod files differ")
    if not lm.get("build_verified") or not rm.get("build_verified"):
        findings.append("At least one mod directory does not match its diagnostic build manifest")
    if any(not m.get(key) for m in (lm, rm) for key in ("game_version", "game_checksum", "language")):
        findings.append("Game version/checksum/language metadata is incomplete")
    stream_results = []
    for name in sorted(left["streams"].keys() | right["streams"].keys()):
        a, b = left["streams"].get(name, []), right["streams"].get(name, [])
        invalid_readings = any("ERROR:" in value or "[" in value or "]" in value
                               for record in a + b for value in record)
        if invalid_readings:
            findings.append(f"Unexpanded localization expressions in {name}; validate runtime logging")
        missing_identity = any(r[1] in ("", "UNKNOWN") for r in a + b)
        if missing_identity:
            findings.append(f"Missing country identity in {name}; per-country comparison is incomplete")
        first = next((i for i in range(max(len(a), len(b)))
                      if (a[i] if i < len(a) else None) != (b[i] if i < len(b) else None)), None)
        # Compare each date/subject independently as well: this distinguishes mere
        # cross-country ordering changes from changed per-country results/counts.
        grouped = []
        ga, gb = defaultdict(list), defaultdict(list)
        for record in a:
            ga[(record[2], record[1])].append((record[0], record[3]))
        for record in b:
            gb[(record[2], record[1])].append((record[0], record[3]))
        for key in sorted(ga.keys() | gb.keys()):
            if ga[key] != gb[key]:
                grouped.append({"date": key[0], "subject": key[1],
                                "left_count": len(ga[key]), "right_count": len(gb[key])})
        stream_results.append({"file": name, "left_records": len(a), "right_records": len(b),
                               "trace_valid": bool(a and b) and not (invalid_readings or missing_identity
                                   or trace_warnings["left"].get(name) or trace_warnings["right"].get(name)),
                               "first_observed_difference": None if first is None else {
                                   "index": first, "left": a[first] if first < len(a) else None,
                                   "right": b[first] if first < len(b) else None},
                               "per_subject_differences": grouped,
                               "left_stage_counts": dict(Counter(r[0] for r in a if r[3] == "event")),
                               "right_stage_counts": dict(Counter(r[0] for r in b if r[3] == "event"))})
    if not left["streams"] or not right["streams"]:
        findings.append("No trace on at least one peer: disabled, unsupported logging, or wrong log/session")
    return {"schema": 1, "findings": findings, "mod_file_differences": differences,
            "trace_warnings": trace_warnings,
            "streams": stream_results,
            "limitation": "Trace differences are observations, not proof of the first simulation divergence. "
                          "Matching traces do not prove synchronization; only selected human-country caches are logged. "
                          "Numeric localization and runtime logging require in-game verification. "
                          "OOS files are preserved for separate analysis, not decoded by this tool."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    package = sub.add_parser("build")
    package.add_argument("--target", choices=("stable", "sol_standalone"), default="stable")
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--trace", action="store_true", help="Enable tracing in exported copy only")
    diff = sub.add_parser("compare")
    diff.add_argument("left", type=Path)
    diff.add_argument("right", type=Path)
    diff.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            build(args.target, args.output, args.trace)
        else:
            result = compare(read_report(args.left), read_report(args.right))
            # Refuse to overwrite evidence, reports, or arbitrary existing files.
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
            print(f"[OK] Comparison: {args.output}")
            for finding in result["findings"]:
                print(f"[NOTE] {finding}")
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

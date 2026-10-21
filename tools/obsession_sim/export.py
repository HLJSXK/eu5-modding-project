"""Export a finished run for the browser playback mode of immunity_lock_viz.html."""

from __future__ import annotations

import json
from pathlib import Path


def playback_payload(sim, title="", note="", start_year=None, milestone_results=None):
    g = sim.g
    if not g.coords:
        raise ValueError("playback needs graph.coords")
    if not sim.frames:
        raise ValueError("run with Params(frames_every=k) to record frames")
    xs = [c[0] for c in g.coords]
    ys = [c[1] for c in g.coords]
    return {
        "format": "obsession_sim.playback/1",
        "title": title, "note": note,
        "nodes": len(g.coords),
        "bounds": g.meta.get("geometry", {}).get("bounds", [min(xs), min(ys), max(xs), max(ys)]),
        "xy": [[round(a, 3), round(b, 3)] for a, b in g.coords],
        "names": g.names,
        "group": g.owner,
        "group_names": g.group_names,
        "attrs": g.attrs,
        "graph_meta": g.meta,
        "start_year": start_year,
        "milestones": milestone_results or [],
        "arrival": sim.arrival,
        "first_positive": sim.first_positive,
        "threshold_arrival": {str(k): v for k, v in sim.threshold_arrival.items()},
        "clock": {**({"deadline": sim.deadline, "history": sim.clock_history} if hasattr(sim,"deadline") else {"join": sim.join}),"joined":[sim.clock_joined(c) for c in range(sim.ng)],
                  "decay_start": sim.decay_start, "finished_month": sim.finished_month},
        "inputs": {"seeds": sim.P.seeds, "scenario": g.meta.get("scenario", {}),
                   "note": "Replay is precomputed; use the local parameter editor to rerun the Python core."},
        "frames": [{"month": t, "stages": s} for t, s in sim.frames],
        "series": sim.series,
        "summary": sim.summary(),
        "params": {k: v for k, v in vars(sim.P).items() if k not in ("seeds", "rho_by_node", "p_by_node")},
    }


def export_playback(sim, path, title="", note="", **kwargs):
    Path(path).write_text(json.dumps(playback_payload(sim, title, note, **kwargs), ensure_ascii=False,
                                     separators=(",", ":")), encoding="utf-8")


def export_html(sim, path, title="", note="", **kwargs):
    """Bundle the existing viewer and a replay into one double-clickable offline report."""
    template = Path(__file__).resolve().parents[2] / "docs/design/obsession/experiments/immunity_lock_viz.html"
    payload = json.dumps(playback_payload(sim, title, note, **kwargs), ensure_ascii=False, separators=(",", ":"))
    # Escaping '<' prevents data from terminating the script element or injecting markup.
    tag = '<script type="application/json" id="obsession-playback-data">' + payload.replace("<", "\\u003c") + '</script>'
    Path(path).write_text(template.read_text(encoding="utf-8").replace("</body>", tag + "\n</body>"), encoding="utf-8")


def mask_holdout_playback(payload, hidden_nodes):
    """Remove held-out geography's outcomes before any playback is written."""
    hidden = set(hidden_nodes)
    payload["masked_nodes"] = sorted(hidden)
    payload["note"] = "拟合集回放；留出范围的强度与到达时间已在导出前屏蔽，节点统计仅含非留出地点。"
    for key in ("arrival", "first_positive", "arrival_kind"):
        if key in payload:
            payload[key] = [(None if key == "arrival_kind" else -1) if i in hidden else v
                            for i, v in enumerate(payload[key])]
    for key, values in payload.get("threshold_arrival", {}).items():
        payload["threshold_arrival"][key] = [-1 if i in hidden else v for i, v in enumerate(values)]
    for frame in payload.get("frames", ()):
        frame["stages"] = "".join("a" if i in hidden else v for i, v in enumerate(frame["stages"]))
    def counts(frame):
        stages = [(ord(c)-97)%7 for i,c in enumerate(frame['stages']) if i not in hidden]
        return dict(members=sum(s>=2 for s in stages), positive=sum(s>=1 for s in stages),
                    x_ge_45=sum(s>=4 for s in stages), saturated=sum(s==6 for s in stages))
    frames = payload.get('frames', [])
    for row in payload.get('series', ()):
        frame = next((f for f in reversed(frames) if f['month']<=row['month']), frames[0] if frames else None)
        if frame is not None:row.update(counts(frame))
    summary = payload.get('summary', {})
    if frames:
        final = counts(frames[-1])
        summary.update(ever_member=sum(t>=0 for t in payload.get('arrival',[]) if t is not None),
                       final_members=final['members'], final_positive=final['positive'], final_saturated=final['saturated'])
    for key in ('groups_joined','groups_finished','calm_month'):summary.pop(key, None)
    payload.pop("clock", None)
    structural = payload.get("structural", {})
    structural["sources"] = [r for r in structural.get("sources", ()) if r.get("node") not in hidden]
    structural["events"] = [r for r in structural.get("events", ()) if r.get("node") not in hidden]
    return payload

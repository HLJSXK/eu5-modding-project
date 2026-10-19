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
        "clock": {"join": sim.join, "decay_start": sim.decay_start, "finished_month": sim.finished_month},
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

"""Loopback-only HTTP runner using the authoritative Python simulation core.

No submitted paths, commands, or file writes are accepted. One worker runs at a
 time; the imported source graph is read once and copied for each scenario.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import threading
from urllib.parse import parse_qs, unquote, urlsplit
import uuid

from .core import Params, Simulation
from .export import playback_payload
from .graph import hex_grid, load_json, voronoi_groups
from .metrics import milestones
from .presets import PRESETS, make_params
from .scenario import apply_scenario

WORKSPACE = Path(__file__).resolve().parents[2]
VIEWER_TEMPLATE = WORKSPACE / "docs/design/obsession/experiments/immunity_lock_viz.html"
PUBLIC_PARAMS = ("rho", "p", "delta", "hold_T", "decay_factor", "habit_floor", "max_months", "budget", "frames_every", "series_every")
ALLOWED_PARAMS = {f.name for f in fields(Params)} - {"seeds", "rho_by_node", "p_by_node", "initial_values", "input_events", "spread_windows", "constraints"}
SWEEP_PARAMS = ("p", "rho", "delta", "hold_T", "decay_factor", "habit_floor", "budget", "seed_value")
MAX_SWEEP_VALUES = 24
INTEGERS = {"hold_T", "max_months", "budget", "frames_every", "series_every", "global_decay_start", "coefficient_cost"}
LIMITS = {"rho": (0, 1), "p": (0, 1), "delta": (0, 100), "eps": (0.000000001, 1),
          "hold_T": (0, 12000), "decay_factor": (0, 1), "habit_floor": (0, 1), "habit_finish_S": (0.000000001, 1),
          "global_decay_start": (-1, 12000), "global_rho": (0, 1), "global_p": (0, 1), "init_all": (0, 100),
          "max_months": (1, 12000), "budget": (1, 10_000_000_000), "frames_every": (1, 12000), "series_every": (1, 12000),
          "coefficient_cost": (0, 1000)}


def _number(value, name, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if integer and int(value) != value:
        raise ValueError(f"{name} must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return int(value) if integer else value


def _finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("JSON numbers must be finite")
    if isinstance(value, dict):
        for child in value.values():
            _finite_json(child)
    elif isinstance(value, list):
        for child in value:
            _finite_json(child)


def _params(values):
    if not isinstance(values, dict):
        raise ValueError("params must be an object")
    unknown = set(values) - ALLOWED_PARAMS
    if unknown:
        raise ValueError("unknown or forbidden Params: " + ", ".join(sorted(unknown)))
    clean = {}
    for key, value in values.items():
        if key == "decay":
            if value not in ("country_clock", "none", "global_node", "global_lazy"):
                raise ValueError("unknown decay model")
            clean[key] = value
        elif key == "stop_when_calm":
            if not isinstance(value, bool):
                raise ValueError("stop_when_calm must be boolean")
            clean[key] = value
        elif key == "budget" and value is None:
            clean[key] = None
        else:
            clean[key] = _number(value, key, *LIMITS[key], integer=key in INTEGERS)
    return clean


def _scenario_shape(scenario, n):
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be an object")
    for section in ("seeds", "coefficients", "routes", "milestones", "initial", "sources", "waves", "wake", "coefficient_events", "constraints", "contacts", "land_corridors"):
        rows = scenario.get(section, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"scenario.{section} must be a list of objects")
        for row in rows:
            if "nodes" in row and (not isinstance(row["nodes"], list) or any(
                    isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < n for v in row["nodes"])):
                raise ValueError("scenario nodes must be valid nonnegative graph indices")


class RunnerServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_close(self):
        if hasattr(self, "job_lock"):
            with self.job_lock:
                for job in self.jobs.values():
                    job["cancel"].set()
        super().server_close()

    def structural_config(self):
        from .experiment import HERE, freeze_status, read_json
        valid, digest, _ = freeze_status()
        worlds = []
        for path in sorted((WORKSPACE / "tmp/obsession_worlds").glob("*/timeline.json")):
            manifest = read_json(path)
            snaps = manifest.get("snapshots", [])
            if snaps:
                worlds.append({"id": manifest["id"], "snapshots": len(snaps),
                               "first_date": snaps[0]["date"], "last_date": snaps[-1]["date"]})
        params=read_json(HERE / "structural_config.json")["params"]
        selected=HERE/'selected_params.json'
        if selected.exists():
            from .structural import validate_params
            values=read_json(selected)
            params={**params,**validate_params(values.get('params',values))}
        return {"params":params, "worlds": worlds,
                "frozen_valid": valid, "frozen_hash": digest}

    def start_structural(self, request):
        from .experiment import Experiment, HERE, read_json
        if not isinstance(request, dict) or set(request) - {"action", "world", "mode", "seed", "params", "fit_only", "force_full"}:
            raise ValueError("unknown structural request fields")
        _finite_json(request)
        action = request.get("action", "run")
        if action not in ("quick", "screen", "run", "matrix", "refresh"):
            raise ValueError("action must be quick, screen, run, matrix or refresh")
        force_full = request.get("force_full", False)
        if not isinstance(force_full, bool):
            raise ValueError("force_full must be boolean")
        mode = request.get("mode", "S")
        if mode not in ("S", "H", "G", "F"):
            raise ValueError("invalid structural mode")
        seed = _number(request.get("seed", 0), "seed", 0, 29, integer=True)
        world = request.get("world", "R")
        choices = {"R"} | {"O:"+w["id"] for w in self.structural_config()["worlds"]}
        if world not in choices:
            raise ValueError("unknown structural world")
        params = request.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("structural params must be an object")
        from .structural import validate_params
        clean = validate_params(params)
        fit_only = request.get("fit_only", True)
        if not isinstance(fit_only, bool):
            raise ValueError("fit_only must be boolean")
        job = {"id":uuid.uuid4().hex, "kind":"structural", "status":"running", "progress":"准备世界输入…",
               "cancel":threading.Event()}
        if not self._claim_slot(job):
            return None
        def work():
            try:
                if action == "refresh":
                    from tools.eu5_save_parser.world_export import archive_worlds
                    def log(message, **_):
                        if job["cancel"].is_set():
                            raise InterruptedError("refresh cancelled")
                        with self.job_lock:
                            job["progress"] = message
                    archive_worlds(WORKSPACE / "data/saves/observer_archive", WORKSPACE / "tmp/obsession_worlds", log)
                    with self.job_lock:
                        job.update(status="complete", progress="新增存档已导入；刷新页面即可选择。")
                    return
                observers = sorted((WORKSPACE / "tmp/obsession_worlds").glob("*/timeline.json"))
                if action in ("quick", "screen", "matrix") and (HERE / "selection_log.json").exists():
                    from .validation import bound_observers
                    observers = bound_observers(HERE / "selection_log.json") or observers
                experiment = Experiment(self.graph_path, observers, WORKSPACE / ".eu5-base/reference_game_files/game",
                                        WORKSPACE / "tmp/obsession_structural")
                def progress(value, run=None, **_):
                    with self.job_lock:
                        if run is None:
                            job["progress"] = str(value)
                        else:
                            job.update(month=value, progress=f"{mode}×{world.split(':')[0]} · {1337+value/12:.0f} 年")
                if action in ("quick", "screen", "matrix"):
                    from .validation import cache_screen, quick_check
                    result = (quick_check if action=="quick" else cache_screen)(
                        experiment, params=clean, progress=progress, cancel=job["cancel"])
                    if action=="matrix" and (force_full or result["decision"]!="early_reject"):
                        result = experiment.matrix(params=clean,progress=progress,cancel=job["cancel"])
                else:
                    result = experiment.one(world,mode,seed,params=clean,fit_only=fit_only,frames=12,
                                            progress=progress,cancel=job["cancel"])
                with self.job_lock:
                    message = ("快速检查通过；不代表历史验收通过。" if action=="quick" else
                               "缓存已证明必要门槛未达；完整矩阵已跳过。" if action=="matrix" and result.get("decision")=="early_reject" else
                               "缓存筛查完成；未启动新模拟。" if action=="screen" else "计算完成；诊断与闸门结论已更新。")
                    job.update(status="complete", result=result, progress=message)
            except InterruptedError:
                with self.job_lock:
                    job.update(status="cancelled", progress="已取消")
            except Exception as exc:
                with self.job_lock:
                    job.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        threading.Thread(target=work,daemon=True).start()
        return job["id"]

    def prepare(self, request, graph=None):
        """Validate a run request. `graph` lets a sweep reuse one copy: scenario routes are idempotent."""
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        _finite_json(request)
        if set(request) - {"map", "preset", "start_year", "seed_name", "seed_value", "params", "scenario"}:
            raise ValueError("unknown run fields")
        map_key = request.get("map", "real")
        if not isinstance(map_key, str) or map_key not in self.graphs:
            raise ValueError("map must be real or hex")
        map_config = self.config["maps"][map_key]
        preset = request.get("preset", map_config["defaults"]["preset"])
        if not isinstance(preset, str) or preset not in PRESETS:
            raise ValueError("unknown preset")
        defaults = map_config["defaults"]
        start_year = _number(request.get("start_year", defaults["start_year"]), "start_year", 1, 9999)
        seed_name = request.get("seed_name", defaults["seed_name"])
        if not isinstance(seed_name, str) or seed_name not in self.node_indices[map_key]:
            raise ValueError("unknown seed_name")
        seed_value = _number(request.get("seed_value", defaults["seed_value"]), "seed_value", 0.000000001, 100)
        overrides = _params(request.get("params", {}))
        overrides.setdefault("frames_every", 12)
        overrides.setdefault("series_every", 12)
        graph = deepcopy(self.graphs[map_key]) if graph is None else graph
        graph.meta["simulation_map"] = map_key
        scenario = deepcopy(request.get("scenario", map_config["scenario"]))
        _scenario_shape(scenario, graph.n)
        overrides = dict(_params(scenario.get("parameters", {})), **overrides)
        base = make_params(preset, **overrides)
        seeds = scenario.get("seeds")
        if seeds is not None and not isinstance(seeds, list):
            raise ValueError("scenario.seeds must be a list")
        if seeds:
            seeds[0] = dict(seeds[0], name=seed_name, value=seed_value)
        elif seeds is None:
            scenario["seeds"] = [{"name": seed_name, "month": 0, "value": seed_value}]
        overrides.update(apply_scenario(graph, scenario, base.p, base.rho, start_year))
        params = make_params(preset, **overrides)
        # Scenario multipliers compound; enforce finiteness after application.
        if params.p_by_node and any(not math.isfinite(p) for p in params.p_by_node):
            raise ValueError("scenario produces nonfinite p_by_node")
        problems = graph.validate()
        if problems:
            raise ValueError("invalid scenario graph: " + "; ".join(problems[:3]))
        return graph, params, preset, start_year, scenario

    def prepare_sweep(self, request):
        """Validate every variant before any work starts; a sweep shares the single job slot."""
        if not isinstance(request, dict):
            raise ValueError("sweep request must be an object")
        _finite_json(request)
        if set(request) - {"run", "param", "values"}:
            raise ValueError("unknown sweep fields")
        base = request.get("run", {})
        if not isinstance(base, dict):
            raise ValueError("sweep.run must be an object")
        param = request.get("param")
        if param not in SWEEP_PARAMS:
            raise ValueError("sweep.param must be one of " + ", ".join(SWEEP_PARAMS))
        values = request.get("values")
        if not isinstance(values, list) or not 1 <= len(values) <= MAX_SWEEP_VALUES:
            raise ValueError(f"sweep.values must list 1 to {MAX_SWEEP_VALUES} values")
        variants = []
        graph = None
        for value in values:
            run = deepcopy(base)
            if param == "seed_value":
                run["seed_value"] = value
            else:
                run["params"] = dict(run.get("params", {}), **{param: value})
            # Sweeps report metrics only: no stage frames, yearly counts for the curve overlay.
            run["params"] = dict(run.get("params", {}), frames_every=1, series_every=12)
            graph, params, preset, start_year, scenario = self.prepare(run, graph)
            params.frames_every = 0
            variants.append((value, graph, params, preset, start_year, scenario))
        return param, variants

    def _claim_slot(self, job):
        with self.job_lock:
            if any(other["status"] == "running" for other in self.jobs.values()):
                return False
            # Keep only the most recent result so large replays cannot pile up.
            self.jobs.clear()
            self.jobs[job["id"]] = job
            return True

    def start_sweep(self, prepared):
        param, variants = prepared
        first = variants[0][1]
        job = {"id": uuid.uuid4().hex, "kind": "sweep", "map": first.meta["simulation_map"], "status": "running",
               "param": param, "values": [v[0] for v in variants], "run_index": 0, "runs": len(variants),
               "month": 0, "max_months": variants[0][2].max_months, "results": [], "cancel": threading.Event()}
        if not self._claim_slot(job):
            return None
        threading.Thread(target=self.run_sweep, args=(job, variants), daemon=True).start()
        return job["id"]

    def run_sweep(self, job, variants):
        try:
            for index, (value, graph, params, preset, start_year, scenario) in enumerate(variants):
                with self.job_lock:
                    job.update(run_index=index, month=0, max_months=params.max_months)
                sim = Simulation(graph, params)
                while not job["cancel"].is_set() and sim.step():
                    with self.job_lock:
                        job["month"] = sim.t
                if job["cancel"].is_set():
                    break
                specs = scenario.get("milestones", [])
                row = {"value": value, "summary": sim.summary(),
                       "milestones": milestones(sim, specs, start_year) if specs else [],
                       "series": [[r["month"], r["members"], r["x_ge_45"]] for r in sim.series]}
                with self.job_lock:
                    job["results"].append(row)
            with self.job_lock:
                job["status"] = "cancelled" if job["cancel"].is_set() else "complete"
        except Exception as exc:
            with self.job_lock:
                job["status"] = "failed"
                job["error"] = f"{type(exc).__name__}: {exc}"

    def start_job(self, prepared):
        graph, params, preset, start_year, scenario = prepared
        job = {"id": uuid.uuid4().hex, "kind": "run", "map": graph.meta["simulation_map"], "status": "running", "month": 0,
               "max_months": params.max_months, "cancel": threading.Event()}
        if not self._claim_slot(job):
            return None
        threading.Thread(target=self.run_job, args=(job, graph, params, preset, start_year, scenario), daemon=True).start()
        return job["id"]

    def run_job(self, job, graph, params, preset, start_year, scenario):
        try:
            sim = Simulation(graph, params)
            while not job["cancel"].is_set() and sim.step():
                with self.job_lock:
                    job["month"] = sim.t
                    # Expose the newest recorded frame so the page can draw the map while computing.
                    if sim.frames and job.get("live", {}).get("month") != sim.frames[-1][0]:
                        row = sim.series[-1] if sim.series else {}
                        job["live"] = {"month": sim.frames[-1][0], "stages": sim.frames[-1][1],
                                       "members": row.get("members"), "x_ge_45": row.get("x_ge_45")}
            if sim.t and (not sim.frames or sim.frames[-1][0] != sim.t - 1):
                sim.frames.append((sim.t - 1, sim.stage_string()))
            payload = None
            if sim.t:
                specs = scenario.get("milestones", [])
                results = milestones(sim, specs, start_year) if specs else []
                map_key = graph.meta["simulation_map"]
                payload = playback_payload(sim, title=scenario.get("title", self.config["maps"][map_key]["graph_name"]) + " · " + preset,
                                           note=scenario.get("note", ""), start_year=start_year, milestone_results=results)
                payload["inputs"]["map"] = map_key
            with self.job_lock:
                job["month"] = sim.t
                job["status"] = "cancelled" if job["cancel"].is_set() else "complete"
                job.pop("live", None)
                if payload:
                    job["payload"] = payload
        except Exception as exc:
            with self.job_lock:
                job["status"] = "failed"
                job["error"] = f"{type(exc).__name__}: {exc}"


def render_preview_html(preview):
    """Read the current frontend on reload instead of freezing it at startup."""
    template = VIEWER_TEMPLATE.read_text(encoding="utf-8")
    embedded = json.dumps(preview, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    return template.replace("</body>", '<script type="application/json" id="obsession-playback-data">' + embedded + '</script>\n</body>').encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WORKSPACE), **kwargs)

    def log_message(self, *_args):
        pass

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def json_response(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def local_request(self, write=False):
        expected = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != expected:
            self.json_response(403, {"error": "Host must match this loopback server"})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://" + expected:
            self.json_response(403, {"error": "Cross-origin requests are disabled; open the viewer from this server"})
            return False
        if write and self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.json_response(415, {"error": "Content-Type must be application/json"})
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        path = urlsplit(self.path).path
        if path == "/api/config":
            self.json_response(200, self.server.config)
        elif path == "/api/structural-config":
            self.json_response(200, self.server.structural_config())
        elif path == "/api/acceptance":
            report = WORKSPACE / "tmp/obsession_structural/matrix.json"
            if not report.exists():
                report = WORKSPACE / "tmp/obsession_structural/cache_screen.json"
            self.json_response(200 if report.exists() else 404,
                               json.loads(report.read_text(encoding="utf-8")) if report.exists() else {"error":"尚无验收或缓存筛查报告"})
        elif path == "/api/preview":
            choices = parse_qs(urlsplit(self.path).query, keep_blank_values=True).get("map", ["real"])
            if len(choices) != 1 or choices[0] not in self.server.previews:
                self.json_response(400, {"error": "map must be real or hex"})
            else:
                self.json_response(200, self.server.previews[choices[0]])
        elif path.startswith("/api/jobs/"):
            job_id = path[len("/api/jobs/"):]
            want_live = parse_qs(urlsplit(self.path).query).get("live", ["0"]) == ["1"]
            with self.server.job_lock:
                job = self.server.jobs.get(job_id)
                result = {k: v for k, v in job.items() if k != "cancel" and (want_live or k != "live")} if job else None
            self.json_response(200 if result else 404, result or {"error": "unknown job"})
        elif path.startswith("/api/"):
            self.json_response(404, {"error": "unknown API endpoint"})
        else:
            if path == "/":
                raw = render_preview_html(self.server.preview)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            resolved = (WORKSPACE / unquote(path).lstrip("/")).resolve()
            allowed = (WORKSPACE / "tmp/obsession_real", WORKSPACE / "tmp/obsession_structural", WORKSPACE / "docs/design/obsession")
            if resolved.suffix.lower() not in (".html", ".css", ".js", ".json") or not any(resolved.is_relative_to(p.resolve()) for p in allowed):
                self.json_response(403, {"error": "Only obsession viewer artifacts are served"})
                return
            super().do_GET()

    def do_HEAD(self):
        self.json_response(405, {"error": "use GET"})

    def do_POST(self):
        if not self.local_request(write=True):
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 262144:
                raise ValueError("request body must be 1 to 262144 bytes")
            request = json.loads(self.rfile.read(size).decode("utf-8"))
            path = urlsplit(self.path).path
            if path in ("/api/run", "/api/sweep", "/api/structural"):
                with self.server.job_lock:
                    busy = any(job["status"] == "running" for job in self.server.jobs.values())
                if busy:
                    self.json_response(409, {"error": "a run is already active; cancel it before starting another"})
                    return
                if path == "/api/structural":
                    job_id = self.server.start_structural(request)
                elif path == "/api/run":
                    job_id = self.server.start_job(self.server.prepare(request))
                else:
                    job_id = self.server.start_sweep(self.server.prepare_sweep(request))
                self.json_response(202 if job_id else 409, {"id": job_id} if job_id else {"error": "a run is already active"})
            elif path.startswith("/api/jobs/") and path.endswith("/cancel"):
                job_id = path[len("/api/jobs/"):-len("/cancel")]
                with self.server.job_lock:
                    job = self.server.jobs.get(job_id)
                    if job:
                        job["cancel"].set()
                        result = {"id": job_id, "status": job["status"]}
                self.json_response(200 if job else 404, result if job else {"error": "unknown job"})
            else:
                self.json_response(404, {"error": "unknown API endpoint"})
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError, RecursionError) as exc:
            self.json_response(400, {"error": str(exc)})


def build_server(graph_path, host="127.0.0.1", port=8765, scenario=None, preset="baseline"):
    """Return an unstarted loopback server; caller owns serve_forever/close."""
    if host != "127.0.0.1":
        raise ValueError("The simulator only binds to 127.0.0.1")
    if preset not in PRESETS:
        raise ValueError("unknown preset")
    graph = load_json(graph_path)
    if graph.validate() or not graph.n or not graph.coords or not graph.names:
        raise ValueError("server requires a valid named graph with coordinates")
    if scenario is None:
        scenario = {}
    elif not isinstance(scenario, dict):
        scenario = json.loads(Path(scenario).read_text(encoding="utf-8-sig"))
    _finite_json(scenario)
    _scenario_shape(scenario, graph.n)
    first_seed = next(iter(scenario.get("seeds", [])), {})
    scenario_params = _params(scenario.get("parameters", {}))
    defaults = {"preset": preset, "start_year": scenario.get("start_year", graph.meta.get("source_year") or 1337),
                "seed_name": first_seed.get("name", graph.names[graph.meta.get("center", 0)]), "seed_value": first_seed.get("value", 25),
                "params": {k: getattr(make_params(preset, **dict(scenario_params, frames_every=12, series_every=12)), k) for k in PUBLIC_PARAMS}}
    server = RunnerServer((host, port), Handler)
    server.graph = graph
    server.graph_path = Path(graph_path).resolve()
    server.node_index = {name: i for i, name in enumerate(graph.names)}
    server.scenario = deepcopy(scenario)
    hex_graph = hex_grid(117, 116)
    hex_graph.names = [f"hex_{row}_{col}" for row in range(116) for col in range(117)]
    hex_graph.owner = voronoi_groups(hex_graph, 1600, seed=20261019)
    hex_graph.group_names = [f"g{i}" for i in range(1600)]
    hex_graph.meta.update({"group_seed": 20261019, "clock_groups": "1600 synthetic graph Voronoi groups"})
    hex_scenario = {"title": "117 × 116 六边形实验地图", "start_year": 1337,
                    "note": "生成的六边形地图与 1600 个 Voronoi 分组；采用同一 Python 扩散核心，不承载历史地区或路线。",
                    "seeds": [{"name": hex_graph.names[hex_graph.meta["center"]], "month": 0, "value": 25}],
                    "coefficients": [], "routes": [], "milestones": []}
    hex_defaults = deepcopy(defaults)
    hex_defaults.update(start_year=1337, seed_name=hex_scenario["seeds"][0]["name"], seed_value=25)
    server.graphs = {"real": graph, "hex": hex_graph}
    server.node_indices = {"real": server.node_index, "hex": {name: i for i, name in enumerate(hex_graph.names)}}
    server.job_lock = threading.Lock()
    server.jobs = {}
    server.config = {"current_map": "real", "nodes": graph.n, "graph_name": Path(graph_path).name,
                     "presets": list(PRESETS), "defaults": defaults,
                     "sweep": {"params": list(SWEEP_PARAMS), "max_values": MAX_SWEEP_VALUES},
                     "preset_defaults": {name: {"doc": PRESETS[name]["doc"],
                         "params": {k: getattr(make_params(name, frames_every=12, series_every=12), k) for k in PUBLIC_PARAMS}}
                         for name in PRESETS}, "scenario": deepcopy(scenario),
                     "maps": {"real": {"label": "EU5 真实地图", "nodes": graph.n, "graph_name": Path(graph_path).name,
                                        "defaults": defaults, "scenario": deepcopy(scenario)},
                              "hex": {"label": "生成六边形地图", "nodes": hex_graph.n, "graph_name": "hex_117x116",
                                       "defaults": hex_defaults, "scenario": hex_scenario}}}
    try:
        server.previews = {}
        for map_key in server.graphs:
            preview_graph, preview_params, _, start_year, _ = server.prepare(
                {"map": map_key, "params": {"max_months": 1, "frames_every": 1, "series_every": 1}})
            preview_sim = Simulation(preview_graph, preview_params).run()
            preview = playback_payload(preview_sim, title=server.config["maps"][map_key]["graph_name"] + " · 预览（尚未完整计算）",
                                       note="当前已加载地图与情景，仅推进 1 个月以展示起点；请设置参数后运行完整模拟。",
                                       start_year=start_year)
            preview["preview"] = True
            preview["inputs"]["map"] = map_key
            server.previews[map_key] = preview
        server.preview = server.previews["real"]
        server.preview_html = render_preview_html(server.preview)
    except Exception:
        server.server_close()
        raise
    return server

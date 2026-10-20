"""HTTP integration tests against small graphs and the Python core."""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from .core import Simulation
from .export import playback_payload
from .graph import from_adjacency, hex_grid, save_json, voronoi_groups
from .presets import make_params
from .scenario import apply_scenario
from . import server as runner_server
from . import experiment as experiment_runner
from .server import build_server


class ServerTests(unittest.TestCase):
    def test_structural_api_validates_and_dispatches_shared_parameters(self):
        invalid=[{"params":{"p":True}},{"params":{"lambda_contact":11}},{"params":{"hold_T":1.2}},
                 {"world":"O:missing"},{"seed":30},{"mode":"bad"},{"fit_only":1},{"command":"bad"}]
        with patch.object(self.server,"structural_config",return_value={"worlds":[]}):
            for value in invalid:
                with self.subTest(value=value):
                    self.assertEqual(400,self.request("POST","/api/structural",value)[0])
            with patch.object(experiment_runner,"Experiment") as cls:
                cls.return_value.one.return_value={"K":[],"world_kind":"R","mode":"S"}
                status,result=self.request("POST","/api/structural",{"params":{"p":.012,"hold_T":600}})
                self.assertEqual(202,status)
                job=self.wait_job(result['id'])
                self.assertEqual('complete',job['status'])
                call=cls.return_value.one.call_args
                self.assertEqual(('R','S',0),call.args)
                self.assertEqual({'p':.012,'hold_T':600},call.kwargs['params'])
                self.assertTrue(call.kwargs['fit_only'])
                self.assertEqual(12,call.kwargs['frames'])

    def test_reloading_root_reads_current_frontend_without_restart(self):
        template = Path(self.temp.name) / "viewer.html"
        with patch.object(runner_server, "VIEWER_TEMPLATE", template):
            for version in ("old frontend", "updated frontend"):
                template.write_text(f"<html><body>{version}</body></html>", encoding="utf-8")
                connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
                connection.request("GET", "/")
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                self.assertEqual(200, response.status)
                self.assertTrue(version in body, "root served a cached frontend")
                self.assertIn('id="obsession-playback-data"', body)
                connection.close()

    def test_explicit_empty_seed_list_and_historical_defaults_survive_prepare(self):
        scenario = {"seeds": [], "parameters": {"p": .004, "hold_T": 600, "coefficient_cost": 10},
                    "initial": [{"names": ["a"], "value": 30}]}
        graph, params, _, _, actual = self.server.prepare({"scenario": scenario})
        self.assertEqual([], params.seeds)
        self.assertEqual([], actual["seeds"])
        self.assertEqual([(0, 30)], params.initial_values)
        self.assertEqual((.004, 600, 10), (params.p, params.hold_T, params.coefficient_cost))
        _, params, _, _, _ = self.server.prepare({"scenario": scenario, "params": {"p": .01}})
        self.assertEqual(.01, params.p)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "tiny.json"
        self.graph = from_adjacency([(1,), (0, 2), (1,), ()], names=["a", "b", "c", "island"],
                                    coords=[(0,0), (1,0), (2,0), (3,0)], owner=[0,0,1,1], group_names=["AA", "BB"])
        save_json(self.graph, self.path)
        self.scenario = {"title": "Fixture", "start_year": 1400,
                         "seeds": [{"name": "a", "month": 0, "value": 25}, {"name": "c", "month": 5, "value": 12}],
                         "coefficients": [{"names": ["b"], "p_scale": 2}],
                         "routes": [{"from": "c", "to": "island", "weight": 0.5}]}
        self.server = build_server(self.path, port=0, scenario=self.scenario)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = dict(headers or {})
        if data is not None:
            headers.setdefault("Content-Type", "application/json")
        connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
        response = connection.getresponse()
        body = response.read()
        status = response.status
        connection.close()
        return status, json.loads(body) if body else None

    def wait_job(self, job_id):
        for _ in range(100):
            status, job = self.request("GET", "/api/jobs/" + job_id)
            self.assertEqual(200, status)
            if job["status"] != "running":
                return job
            time.sleep(.01)
        self.fail("job did not finish")

    def test_config_and_run_equal_authoritative_core(self):
        status, config = self.request("GET", "/api/config")
        self.assertEqual(200, status)
        self.assertEqual(4, config["nodes"])
        self.assertEqual("real", config["current_map"])
        self.assertEqual(config["defaults"], config["maps"]["real"]["defaults"])
        self.assertEqual(self.scenario, config["scenario"])
        self.assertEqual(1400, config["defaults"]["start_year"])
        self.assertIn("baseline_T120", config["presets"])
        self.assertEqual(120, config["preset_defaults"]["baseline_T120"]["params"]["hold_T"])
        status, preview = self.request("GET", "/api/preview")
        self.assertEqual(200, status)
        self.assertTrue(preview["preview"])
        self.assertEqual(4, preview["nodes"])
        self.assertEqual([], preview["milestones"])
        self.assertEqual(1, preview["summary"]["months"])
        values = {"max_months": 24, "frames_every": 7, "series_every": 3, "p": .04, "hold_T": 10}
        status, result = self.request("POST", "/api/run", {"params": values, "seed_name": "b", "seed_value": 30})
        self.assertEqual(202, status)
        job = self.wait_job(result["id"])
        self.assertEqual("complete", job["status"])
        self.assertEqual("real", job["map"])
        self.assertEqual("real", job["payload"]["inputs"]["map"])
        self.assertEqual("real", job["payload"]["graph_meta"]["simulation_map"])
        graph = deepcopy(self.graph)
        scenario = deepcopy(self.scenario)
        scenario["seeds"][0].update(name="b", value=30)
        params = make_params("baseline", **values)
        scenario_params = apply_scenario(graph, scenario, params.p, params.rho, 1400)
        expected = playback_payload(Simulation(graph, make_params("baseline", **values, **scenario_params)).run(), start_year=1400)
        for key in ("frames", "summary", "arrival", "clock", "series", "params"):
            self.assertEqual(expected[key], job["payload"][key], key)
        self.assertEqual(23, job["payload"]["frames"][-1]["month"])
        self.assertNotIn("scenario", self.server.graph.meta)
        self.assertEqual(self.graph.outgoing, self.server.graph.outgoing)
        self.assertEqual(self.scenario, self.server.scenario)

    def test_map_previews_and_hex_run_use_same_core_without_real_scenario(self):
        _, config = self.request("GET", "/api/config")
        hex_config = config["maps"]["hex"]
        self.assertEqual(13572, hex_config["nodes"])
        self.assertEqual("hex_58_58", hex_config["defaults"]["seed_name"])
        for key in ("coefficients", "routes", "milestones"):
            self.assertEqual([], hex_config["scenario"][key])
        self.assertEqual(self.scenario, config["maps"]["real"]["scenario"])
        for map_key, nodes in (("real", 4), ("hex", 13572)):
            status, preview = self.request("GET", f"/api/preview?map={map_key}")
            self.assertEqual(200, status)
            self.assertEqual(nodes, preview["nodes"])
            self.assertEqual(map_key, preview["inputs"]["map"])
            self.assertEqual(map_key, preview["graph_meta"]["simulation_map"])
            self.assertEqual(nodes, len(preview["frames"][0]["stages"]))
        self.assertEqual(400, self.request("GET", "/api/preview?map=unknown")[0])
        self.assertEqual(400, self.request("GET", "/api/preview?map=real&map=hex")[0])
        values = {"max_months": 4, "frames_every": 2, "series_every": 1, "p": .04}
        _, result = self.request("POST", "/api/run", {"map": "hex", "params": values})
        job = self.wait_job(result["id"])
        self.assertEqual("complete", job["status"])
        self.assertEqual("hex", job["map"])
        payload = job["payload"]
        self.assertEqual("hex_grid", payload["graph_meta"]["kind"])
        self.assertEqual("hex", payload["inputs"]["map"])
        self.assertEqual(1600, len(payload["group_names"]))
        self.assertTrue(all(name.startswith("hex_") for name in payload["names"]))
        self.assertEqual([], payload["milestones"])
        graph = hex_grid(117, 116)
        graph.owner = voronoi_groups(graph, 1600, seed=20261019)
        expected = Simulation(graph, make_params("baseline", center=graph.meta["center"], **values)).run()
        self.assertEqual(expected.summary(), payload["summary"])
        self.assertEqual(expected.arrival, payload["arrival"])
        self.assertEqual([{"month": t, "stages": stages} for t, stages in expected.frames], payload["frames"])
        # Switching back restores the original real geography and scenario.
        _, result = self.request("POST", "/api/run", {"map": "real", "params": values})
        real_job = self.wait_job(result["id"])
        self.assertEqual("real", real_job["map"])
        self.assertEqual(4, real_job["payload"]["nodes"])
        self.assertEqual(self.scenario, self.server.scenario)

    def test_finite_ranges_whitelist_and_errors(self):
        bad = [{"params": {"p": float("nan")}}, {"params": {"rho": float("inf")}},
               {"params": {"max_months": 12001}}, {"params": {"max_months": 1.5}},
               {"params": {"frames_every": 0}}, {"params": {"budget": -1}},
               {"params": {"rho_by_node": [1,2]}}, {"params": {"seeds": []}},
               {"params": {"p": True}}, {"seed_name": "missing"}, {"preset": "missing"},
               {"params": {"decay": "bad"}}, {"command": "anything"}, {"scenario": []},
               {"scenario": {"seeds": [1]}}, {"scenario": {"coefficients": [{"nodes": [-1], "p_scale": 1}]}},
               {"map": "unknown"}, {"map": None}, {"map": []}]
        for request in bad:
            with self.subTest(request=request):
                self.assertEqual(400, self.request("POST", "/api/run", request)[0])
        self.assertEqual(404, self.request("GET", "/api/jobs/missing")[0])
        self.assertEqual(404, self.request("POST", "/api/jobs/missing/cancel", {})[0])

    def test_single_job_cancellation_and_new_run_independence(self):
        old_step = Simulation.step
        entered = threading.Event()
        def slow_step(sim):
            entered.set()
            time.sleep(.02)
            return old_step(sim)
        with patch.object(Simulation, "step", new=slow_step):
            status, result = self.request("POST", "/api/run", {"params": {"max_months": 12000, "stop_when_calm": False}})
            self.assertEqual(202, status)
            self.assertTrue(entered.wait(1))
            self.assertEqual(409, self.request("POST", "/api/run", {})[0])
            self.assertEqual(409, self.request("POST", "/api/run", {"map": "hex"})[0])
            self.assertEqual(200, self.request("POST", f"/api/jobs/{result['id']}/cancel", {})[0])
            job = self.wait_job(result["id"])
            self.assertEqual("cancelled", job["status"])
            self.assertLess(job["month"], 12000)
            if job.get("payload"):
                self.assertEqual(job["month"] - 1, job["payload"]["frames"][-1]["month"])
        status, result = self.request("POST", "/api/run", {"params": {"max_months": 2}, "scenario": {}})
        self.assertEqual(202, status)
        self.assertEqual("complete", self.wait_job(result["id"])["status"])

    def test_sweep_matches_individual_core_runs(self):
        milestone = [{"name": "c reached", "names": ["c"], "threshold": 1, "target_month": 6, "tolerance_months": 3}]
        scenario = dict(deepcopy(self.scenario), milestones=milestone)
        base = {"params": {"max_months": 30, "hold_T": 10}, "scenario": scenario}
        status, result = self.request("POST", "/api/sweep", {"run": base, "param": "p", "values": [.01, .04, .08]})
        self.assertEqual(202, status)
        job = self.wait_job(result["id"])
        self.assertEqual("complete", job["status"])
        self.assertEqual("sweep", job["kind"])
        self.assertEqual([.01, .04, .08], [row["value"] for row in job["results"]])
        for row in job["results"]:
            graph = deepcopy(self.graph)
            values = {"max_months": 30, "hold_T": 10, "p": row["value"], "series_every": 12}
            params = make_params("baseline", **values)
            extra = apply_scenario(graph, scenario, params.p, params.rho, 1400)
            sim = Simulation(graph, make_params("baseline", **values, **extra)).run()
            self.assertEqual(sim.summary(), row["summary"])
            self.assertEqual([[r["month"], r["members"], r["x_ge_45"]] for r in sim.series], row["series"])
            self.assertEqual(1, len(row["milestones"]))
        # Seed strength is sweepable too, and replaces only the first seed.
        _, result = self.request("POST", "/api/sweep", {"run": base, "param": "seed_value", "values": [1, 50]})
        job = self.wait_job(result["id"])
        self.assertEqual("complete", job["status"])
        self.assertEqual(2, len(job["results"]))
        # The server's source graph is never altered by sweeps.
        self.assertEqual(self.graph.outgoing, self.server.graph.outgoing)
        bad = [{"param": "frames_every", "values": [1]}, {"param": "p", "values": []},
               {"param": "p", "values": [0.1] * 25}, {"param": "p", "values": [2]},
               {"param": "p", "values": [.01], "extra": 1}, {"param": "p", "values": [.01], "run": {"seed_name": "nope"}}]
        for request in bad:
            with self.subTest(request=request):
                self.assertEqual(400, self.request("POST", "/api/sweep", request)[0])

    def test_running_job_exposes_live_frame_only_on_request(self):
        old_step = Simulation.step
        def slow_step(sim):
            time.sleep(.01)
            return old_step(sim)
        with patch.object(Simulation, "step", new=slow_step):
            _, result = self.request("POST", "/api/run", {"params": {"max_months": 400, "frames_every": 2, "stop_when_calm": False}})
            live = None
            for _ in range(200):
                _, plain = self.request("GET", f"/api/jobs/{result['id']}")
                self.assertNotIn("live", plain)
                _, job = self.request("GET", f"/api/jobs/{result['id']}?live=1")
                if job.get("live"):
                    live = job["live"]
                    break
                time.sleep(.01)
            self.assertIsNotNone(live)
            self.assertEqual(4, len(live["stages"]))
            self.assertEqual(0, live["month"] % 2)
            self.request("POST", f"/api/jobs/{result['id']}/cancel", {})
            job = self.wait_job(result["id"])
            self.assertNotIn("live", job)

    def test_same_origin_and_static_paths(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(200, self.request("GET", "/api/config", headers={"Origin": origin})[0])
        self.assertEqual(403, self.request("POST", "/api/run", {}, {"Origin": "http://evil.invalid"})[0])
        self.assertEqual(403, self.request("POST", "/api/run", {}, {"Origin": "null"})[0])
        self.assertEqual(403, self.request("GET", "/api/config", headers={"Host": "evil.invalid"})[0])
        self.assertEqual(415, self.request("POST", "/api/run", {}, {"Content-Type": "text/plain"})[0])
        for path in ("/CLAUDE.md", "/.git/config", "/tmp/obsession_real/../../CLAUDE.md", "/docs/design/obsession/../../../.git/config"):
            self.assertEqual(403, self.request("GET", path)[0])
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", "/docs/design/obsession/experiments/immunity_lock_viz.html")
        response = connection.getresponse()
        self.assertEqual(200, response.status)
        self.assertIn(b"<html", response.read().lower())
        connection.close()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", "/")
        response = connection.getresponse()
        self.assertEqual(200, response.status)
        body = response.read()
        self.assertIn(b"obsession-playback-data", body)
        self.assertIn(b'"preview":true', body)
        self.assertIn(b'"nodes":4', body)
        connection.close()
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            build_server(self.path, host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()

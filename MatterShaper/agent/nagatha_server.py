#!/usr/bin/env python3
"""
nagatha_server.py — Local web interface for Nagatha
=====================================================

A lightweight Python stdlib server that:
  • Serves the render gallery at http://localhost:7734
  • Accepts natural-language commands from the browser
  • Runs nagatha.py as a subprocess and streams stdout back in real time

No pip dependencies. Pure stdlib.

Usage
─────
    python agent/nagatha_server.py
    python agent/nagatha_server.py --port 8080
    python agent/nagatha_server.py --model llama3.2:3b --no-open

Then open: http://localhost:7734

Command syntax (type in the browser):
    banana                          → map the object "banana"
    compose a table with a candle   → compose a scene
    list                            → list the library
    scenes                          → list saved scenes
    find apple                      → search for "apple"
    fetch banana                    → pull Wikidata data for banana
    report                          → show Wikidata cache summary
"""

import argparse
import http.server
import json
import mimetypes
import os
import queue
import re
import socketserver
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

# ── Paths ─────────────────────────────────────────────────────────────────────

AGENT_DIR   = Path(__file__).parent
PROJECT_DIR = AGENT_DIR.parent            # MatterShaper/
QUARKSUM_DIR= PROJECT_DIR.parent          # quarksum/
GALLERY_HTML= QUARKSUM_DIR / "render_gallery.html"
DEFAULT_PORT= 7734

# ── Job manager ───────────────────────────────────────────────────────────────

class JobManager:
    """Runs subprocesses and streams their stdout via SSE."""

    def __init__(self):
        self._jobs = {}
        self._lock  = threading.Lock()

    def start(self, cmd, cwd=None):
        """Spawn cmd, return job_id immediately."""
        job_id  = uuid.uuid4().hex[:8]
        q       = queue.Queue()
        env     = os.environ.copy()
        proc    = subprocess.Popen(
            cmd, cwd=str(cwd or PROJECT_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=env,
        )
        job = {
            "proc":      proc,
            "queue":     q,
            "lines":     [],
            "done":      False,
            "exit_code": None,
            "started":   time.time(),
            "cmd":       " ".join(str(c) for c in cmd),
        }
        with self._lock:
            self._jobs[job_id] = job

        def _reader():
            try:
                for raw in proc.stdout:
                    line = raw.rstrip()
                    with self._lock:
                        job["lines"].append(line)
                    q.put(("line", line))
            finally:
                proc.wait()
                with self._lock:
                    job["done"]      = True
                    job["exit_code"] = proc.returncode
                q.put(("done", proc.returncode))

        threading.Thread(target=_reader, daemon=True).start()
        return job_id

    def stream(self, job_id):
        """Generator of SSE-formatted strings.  Blocks until job finishes."""
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            yield "data: [error: unknown job]\n\nevent: done\ndata: 1\n\n"
            return
        q = job["queue"]
        while True:
            try:
                kind, payload = q.get(timeout=45)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if kind == "line":
                # Escape for SSE: newlines in data must be encoded
                safe = payload.replace("\\", "\\\\")
                yield f"data: {safe}\n\n"
            elif kind == "done":
                yield f"event: done\ndata: {payload}\n\n"
                break

    def status(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id, {})
        return {
            "job_id":    job_id,
            "running":   not job.get("done", True),
            "exit_code": job.get("exit_code"),
            "cmd":       job.get("cmd", ""),
            "line_count":len(job.get("lines", [])),
        }

    def kill(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id, {})
        proc = job.get("proc")
        if proc and not job.get("done"):
            proc.terminate()


JOBS = JobManager()

# ── Ollama model detection ─────────────────────────────────────────────────────

_MODEL_CACHE = None

def detect_model(override=None):
    global _MODEL_CACHE
    if override:
        _MODEL_CACHE = override
        return override
    if _MODEL_CACHE:
        return _MODEL_CACHE
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        ).stdout
        lines  = [l for l in out.strip().split("\n")[1:] if l.strip()]
        models = [l.split()[0] for l in lines]
        # Prefer models in this quality order
        prefer = ["llama3.1", "llama3.2", "qwen2.5", "gemma2",
                  "mistral", "deepseek", "phi3"]
        for pref in prefer:
            for m in models:
                if pref in m.lower():
                    _MODEL_CACHE = m
                    return m
        if models:
            _MODEL_CACHE = models[0]
            return models[0]
    except Exception:
        pass
    return "llama3.1:8b"


def list_models():
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        ).stdout
        lines = [l for l in out.strip().split("\n")[1:] if l.strip()]
        return [l.split()[0] for l in lines]
    except Exception:
        return []

# ── System info ───────────────────────────────────────────────────────────────

def get_sysinfo():
    """Return cpu%, mem%, disk% for the host machine."""
    import shutil, platform, os
    result = {"cpu": 0, "mem": 0, "disk": 0}
    try:
        u = shutil.disk_usage('/')
        result["disk"] = round(100 * u.used / u.total)
    except Exception:
        pass
    try:
        if platform.system() == "Darwin":
            vm = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=2
            ).stdout
            pages = {}
            for line in vm.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    try:
                        pages[k.strip()] = int(v.strip().rstrip("."))
                    except ValueError:
                        pass
            active = pages.get("Pages active", 0)
            wired  = pages.get("Pages wired down", 0)
            comp   = pages.get("Pages occupied by compressor", 0)
            free   = pages.get("Pages free", 0)
            inact  = pages.get("Pages inactive", 0)
            spec   = pages.get("Pages speculative", 0)
            total  = active + wired + comp + free + inact + spec
            if total > 0:
                result["mem"] = round(100 * (active + wired + comp) / total)
            ps  = subprocess.run(
                ["ps", "-A", "-o", "%cpu"], capture_output=True, text=True, timeout=2
            ).stdout
            vals = []
            for l in ps.strip().splitlines()[1:]:
                try:
                    vals.append(float(l.strip()))
                except ValueError:
                    pass
            ncpus = os.cpu_count() or 1
            result["cpu"] = min(100, round(sum(vals) / ncpus))
        else:
            with open("/proc/meminfo") as f:
                minfo = {}
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        minfo[k.strip()] = v.strip()
            total_kb = int(minfo.get("MemTotal",     "0 kB").split()[0])
            avail_kb = int(minfo.get("MemAvailable", "0 kB").split()[0])
            if total_kb:
                result["mem"] = round(100 * (1 - avail_kb / total_kb))
            with open("/proc/stat") as f:
                vals = list(map(int, f.readline().split()[1:]))
            idle  = vals[3]
            total = sum(vals)
            result["cpu"] = round(100 * (1 - idle / total)) if total else 0
    except Exception:
        pass
    return result


# ── Inventory checker ─────────────────────────────────────────────────────────

_PHI = (1.0 + 5 ** 0.5) / 2
THETA_NATURAL = round(1.0 / _PHI ** 2, 5)   # = 1/φ² ≈ 0.38197  (BH Claying threshold)

_STOP = {
    "a","an","the","on","in","at","with","and","or","of","some","few","many",
    "near","next","to","above","below","behind","beside","between","inside",
    "outside","scene","compose","render","show","me","please","create","make",
    "build","generate","there","is","are","it","its","by","lit","from","for",
    "up","have","has","been","that","this","these","those","my","your","our",
    "their","one","two","three","four","five","wooden","glass","metal","small",
    "large","big","old","new","round","flat","tall","short","open","closed",
}

def check_inventory(description=None):
    """Return object library contents and optionally match against a description."""
    om_dir = PROJECT_DIR / "object_maps"
    objects = sorted(f.stem for f in om_dir.glob("*.shape.json")) if om_dir.exists() else []

    needed, have, missing = [], [], []
    if description:
        words = re.sub(r"[^a-z\s]", "", description.lower()).split()
        nouns = list(dict.fromkeys(w for w in words if w not in _STOP and len(w) > 2))
        for noun in nouns:
            if any(noun in o or o in noun or noun.replace(" ", "_") == o for o in objects):
                have.append(noun)
            else:
                missing.append(noun)
        needed = nouns

    return {
        "library_count": len(objects),
        "library":        objects,
        "needed":         needed,
        "have":           have,
        "missing":        missing,
        "theta_natural":  THETA_NATURAL,
        "theta_label":    "1/φ² — BH Claying complexity threshold",
    }


# ── Command intent parser ─────────────────────────────────────────────────────

def parse_command(text, model):
    """Map natural-language text → nagatha.py / fetch_wikidata.py CLI args."""
    text  = text.strip()
    lower = text.lower()

    py    = sys.executable
    nag   = str(AGENT_DIR / "nagatha.py")
    fetch = str(AGENT_DIR / "fetch_wikidata.py")
    base  = [py, nag, "--backend", "ollama", "--model", model]

    if lower in ("list", "ls", "library", "show library"):
        return base + ["--list"]

    if lower in ("scenes", "list scenes", "show scenes"):
        return base + ["--scenes"]

    if lower.startswith("find "):
        query = text.split(" ", 1)[1]
        return base + ["--find", query]

    if lower.startswith(("compose ", "scene ")):
        desc = text.split(" ", 1)[1]
        return base + ["--compose", desc, "--approve", "auto"]

    if lower.startswith("fix "):
        key = text.split(" ", 1)[1]
        return base + ["--fix", key]

    if lower == "report":
        return [py, fetch, "--report"]

    if lower.startswith("fetch "):
        obj = text.split(" ", 1)[1]
        return [py, fetch, obj]

    if lower in ("fetch all", "fetch --all"):
        return [py, fetch, "--all"]

    # Default: treat as object name to map
    return base + [text, "--approve", "auto"]

# ── Render scanner ────────────────────────────────────────────────────────────

# Preview frames we don't want cluttering the gallery
_SKIP_PATTERNS = ["_preview-", "wg_f03-", "_frame-"]

def scan_renders():
    """Return list of render dicts found under QUARKSUM_DIR."""
    exts = {".png", ".gif", ".html"}
    scan = [
        (QUARKSUM_DIR / "renders",               "Official Renders"),
        (QUARKSUM_DIR / "MatterShaper" / "misc",  "MatterShaper"),
        (QUARKSUM_DIR / "misc",                   "Quarksum Misc"),
        (QUARKSUM_DIR / "theory",                 "Theory"),
        (QUARKSUM_DIR,                            "Quarksum Root"),
    ]
    seen, results = set(), []
    for dirpath, cat in scan:
        if not dirpath.exists():
            continue
        for f in sorted(dirpath.iterdir()):
            if f.suffix.lower() not in exts:
                continue
            if any(pat in f.name for pat in _SKIP_PATTERNS):
                continue
            rel = f.relative_to(QUARKSUM_DIR).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            results.append({
                "path":     rel,
                "name":     f.stem.replace("_", " ").replace("-", " ").title(),
                "type":     f.suffix.lower().lstrip("."),
                "category": cat,
                "mtime":    f.stat().st_mtime,
            })
    return results

# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Quiet — only log errors
        if args and str(args[1]) not in ("200", "304"):
            sys.stderr.write(f"  [{args[1]}] {args[0] % args[1:]}\n")

    # ── CORS ─────────────────────────────────────────────────────────────────

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        path = Path(path)
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        data = path.read_bytes()
        mime, _ = mimetypes.guess_type(str(path))
        self.send_response(200)
        self.send_header("Content-Type",   mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control",  "no-cache")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        # ── API ──────────────────────────────────────────────────────────────

        if path == "/api/ping":
            model  = detect_model()
            models = list_models()
            self._json({"ok": True, "model": model, "models": models})
            return

        if path == "/api/renders":
            self._json(scan_renders())
            return

        if path == "/api/sysinfo":
            self._json(get_sysinfo())
            return

        if path == "/api/inventory":
            qs   = parse_qs(urlparse(self.path).query)
            desc = qs.get("desc", [""])[0]
            self._json(check_inventory(desc or None))
            return

        if path.startswith("/api/stream/"):
            job_id = path.rsplit("/", 1)[-1]
            self.send_response(200)
            self.send_header("Content-Type",    "text/event-stream")
            self.send_header("Cache-Control",   "no-cache")
            self.send_header("X-Accel-Buffering","no")
            self._cors()
            self.end_headers()
            try:
                for chunk in JOBS.stream(job_id):
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if path.startswith("/api/status/"):
            job_id = path.rsplit("/", 1)[-1]
            self._json(JOBS.status(job_id))
            return

        # ── Static files ─────────────────────────────────────────────────────

        if path in ("/", "/index.html"):
            self._file(GALLERY_HTML)
            return

        # Safety: only serve files under QUARKSUM_DIR
        rel  = unquote(path.lstrip("/"))
        fpath= (QUARKSUM_DIR / rel).resolve()
        try:
            fpath.relative_to(QUARKSUM_DIR.resolve())
        except ValueError:
            self.send_response(403)
            self.end_headers()
            return
        self._file(fpath)

    # ── POST ──────────────────────────────────────────────────────────────────

    def do_POST(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode() if length else "{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        if path == "/api/run":
            text  = data.get("command", "").strip()
            model = data.get("model") or detect_model()
            if not text:
                self._json({"error": "empty command"}, 400)
                return
            cmd    = parse_command(text, model)
            job_id = JOBS.start(cmd)
            print(f"  ▶ [{job_id}] {' '.join(str(c) for c in cmd)}")
            self._json({"job_id": job_id, "cmd": " ".join(str(c) for c in cmd)})
            return

        if path == "/api/kill":
            JOBS.kill(data.get("job_id", ""))
            self._json({"ok": True})
            return

        self._json({"error": "not found"}, 404)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port",     type=int, default=DEFAULT_PORT)
    p.add_argument("--model",    default=None, help="Force a specific Ollama model")
    p.add_argument("--no-open",  action="store_true",
                   help="Don't auto-open the browser")
    args = p.parse_args()

    model  = detect_model(args.model)
    models = list_models()

    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║         N A G A T H A                ║")
    print(f"  ║   Web Interface                      ║")
    print(f"  ╚══════════════════════════════════════╝")
    print(f"\n  Gallery : http://localhost:{args.port}")
    print(f"  Model   : {model}")
    if models:
        print(f"  Available: {', '.join(models)}")
    print(f"  Root    : {QUARKSUM_DIR}")
    print(f"\n  Ctrl-C to stop.\n")

    if not args.no_open:
        def _open():
            time.sleep(0.5)
            try:
                import webbrowser
                webbrowser.open(f"http://localhost:{args.port}")
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    server = socketserver.ThreadingTCPServer(("", args.port), Handler)
    server.allow_reuse_address = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping. Goodbye.\n")
        server.shutdown()


if __name__ == "__main__":
    main()

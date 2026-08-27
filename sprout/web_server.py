from __future__ import annotations

import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .bytecode import FunctionObject, disassemble
from .compiler import compile_source
from .errors import SproutError
from .vm import VM


WEB_ROOT = Path(__file__).with_name("web")
MAX_REQUEST_BYTES = 1_000_000
DEFAULT_INSTRUCTION_LIMIT = 100_000
MAX_TRACE_LINES = 2_500


def run_playground(
    source: str,
    trace: bool = False,
    instruction_limit: int = DEFAULT_INSTRUCTION_LIMIT,
) -> dict[str, Any]:
    output: list[str] = []
    trace_lines: list[str] = []
    dropped_trace_lines = 0
    started = time.perf_counter()
    function: FunctionObject | None = None

    def collect_trace(line: str) -> None:
        nonlocal dropped_trace_lines
        if len(trace_lines) < MAX_TRACE_LINES:
            trace_lines.append(line)
        else:
            dropped_trace_lines += 1

    vm = VM(
        output.append,
        trace=trace,
        trace_output=collect_trace,
        instruction_limit=instruction_limit,
    )
    try:
        function = compile_source(source, "playground")
        vm.interpret(function)
        return {
            "ok": True,
            "output": "\n".join(output),
            "bytecode": disassemble(function),
            "trace": _format_trace(trace_lines, dropped_trace_lines),
            "stats": {
                "compiledInstructions": _instruction_count(function),
                "executedInstructions": vm.instructions_executed,
                "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
            },
        }
    except SproutError as error:
        return {
            "ok": False,
            "error": str(error),
            "output": "\n".join(output),
            "bytecode": disassemble(function) if function else "",
            "trace": _format_trace(trace_lines, dropped_trace_lines),
            "stats": {
                "compiledInstructions": _instruction_count(function) if function else 0,
                "executedInstructions": vm.instructions_executed,
                "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
            },
        }


def _instruction_count(function: FunctionObject) -> int:
    total = len(function.chunk.code)
    for constant in function.chunk.constants:
        if isinstance(constant, FunctionObject):
            total += _instruction_count(constant)
    return total


def _format_trace(lines: list[str], dropped: int) -> str:
    if dropped:
        lines = [*lines, "", f"… trace truncated ({dropped:,} additional lines) …"]
    return "\n".join(lines)


class PlaygroundHandler(BaseHTTPRequestHandler):
    server_version = "SproutPlayground/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_file("index.html", "text/html; charset=utf-8")
        elif path == "/styles.css":
            self._serve_file("styles.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_file("app.js", "text/javascript; charset=utf-8")
        elif path == "/health":
            self._send_json({"status": "ok", "runtime": "sprout-vm"})
        elif path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/run":
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                self._send_json({"error": "Request body is empty or too large."}, HTTPStatus.BAD_REQUEST)
                return
            payload = json.loads(self.rfile.read(length))
            source = payload.get("source")
            trace = payload.get("trace", False)
            if not isinstance(source, str) or not isinstance(trace, bool):
                self._send_json({"error": "Expected source text and a boolean trace option."}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(run_playground(source, trace))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"error": "Invalid JSON request."}, HTTPStatus.BAD_REQUEST)

    def _serve_file(self, name: str, content_type: str) -> None:
        try:
            data = (WEB_ROOT / name).read_bytes()
        except OSError:
            self._send_json({"error": "Frontend asset is missing."}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        print(f"[web] {self.address_string()} - {format % args}")


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), PlaygroundHandler)
    print(f"Sprout Playground running at http://{host}:{server.server_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Sprout Playground.")
    finally:
        server.server_close()

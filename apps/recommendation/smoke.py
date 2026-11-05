#!/usr/bin/env python3
"""Exercise the image with real gRPC, flag evaluation, and rapid OTLP exports.

Usage: python apps/recommendation/smoke.py IMAGE [--seconds 120]
Requires grpcio and grpcio-tools. All Docker resources are removed on exit.
"""
import argparse
from concurrent import futures
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import grpc
from grpc_tools import protoc

ROOT = Path(__file__).resolve().parents[2]


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def main(image, seconds):
    with tempfile.TemporaryDirectory() as generated:
        proto = ROOT / "pb/demo.proto"
        if protoc.main(["protoc", f"-I{proto.parent}", f"--python_out={generated}",
                        f"--grpc_python_out={generated}", str(proto)]) != 0:
            raise RuntimeError("protobuf compilation failed")
        sys.path.insert(0, generated)
        import demo_pb2 as pb
        import demo_pb2_grpc as rpc

        received = set()
        flag_calls = 0
        lock = threading.Lock()
        stop = threading.Event()
        backend = grpc.server(futures.ThreadPoolExecutor(max_workers=12))
        ids = {f"product-{n}" for n in range(8)}

        class Catalog(rpc.ProductCatalogServiceServicer):
            def ListProducts(self, request, context):
                return pb.ListProductsResponse(
                    products=[pb.Product(id=value, name=value) for value in sorted(ids)])

        rpc.add_ProductCatalogServiceServicer_to_server(Catalog(), backend)
        # Minimal flagd v1 wire fixtures: ready event and false/DYNAMIC response.
        # DYNAMIC deliberately exercises the RPC on every request (no static cache).
        def events(request, context):
            yield b"\x0a\x0eprovider_ready"
            while context.is_active() and not stop.wait(.1):
                pass
        def resolve_flag(request, context):
            nonlocal flag_calls
            with lock:
                flag_calls += 1
            return b"\x12\x07DYNAMIC"
        backend.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(
            "flagd.evaluation.v1.Service", {
                "ResolveBoolean": grpc.unary_unary_rpc_method_handler(
                    resolve_flag),
                "EventStream": grpc.unary_stream_rpc_method_handler(events),
            }),))
        for signal, api in (("traces", "trace"), ("metrics", "metrics"), ("logs", "logs")):
            def export(payload, context, signal=signal):
                if b"recommendation" in payload:
                    with lock:
                        received.add(signal)
                return b""
            backend.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(
                f"opentelemetry.proto.collector.{api}.v1.{api.capitalize()}Service",
                {"Export": grpc.unary_unary_rpc_method_handler(export)}),))
        port = backend.add_insecure_port("0.0.0.0:0")
        backend.start()
        name = "recommendation-smoke-" + uuid.uuid4().hex[:12]
        channel = None
        try:
            env = {
                "RECOMMENDATION_PORT": "8080",
                "PRODUCT_CATALOG_ADDR": f"host.docker.internal:{port}",
                "FLAGD_HOST": "host.docker.internal",
                "FLAGD_PORT": str(port),
                "OTEL_SERVICE_NAME": "recommendation",
                "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://host.docker.internal:{port}",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                "OTEL_PYTHON_LOG_CORRELATION": "true",
                "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
                "PYTHONFAULTHANDLER": "1",
                "OTEL_METRIC_EXPORT_INTERVAL": "100",
                "OTEL_BSP_SCHEDULE_DELAY": "100",
                "OTEL_BLRP_SCHEDULE_DELAY": "100",
            }
            args = ["docker", "run", "-d", "--name", name, "--memory=500m",
                    "--add-host", "host.docker.internal:host-gateway",
                    "-p", "127.0.0.1::8080"]
            for key, value in env.items():
                args += ["-e", f"{key}={value}"]
            command(*args, image)
            exposed = command("docker", "port", name, "8080/tcp").rsplit(":", 1)[1]
            channel = grpc.insecure_channel("127.0.0.1:" + exposed)
            grpc.channel_ready_future(channel).result(timeout=60)
            stub = rpc.RecommendationServiceStub(channel)
            health = channel.unary_unary("/grpc.health.v1.Health/Check")
            assert health(b"", timeout=5) == b"\x08\x01"
            deadline = time.monotonic() + seconds

            def exercise(_):
                count = 0
                while time.monotonic() < deadline:
                    response = stub.ListRecommendations(
                        pb.ListRecommendationsRequest(product_ids=["product-0"]), timeout=10)
                    returned = set(response.product_ids)
                    assert len(returned) == 5 and returned <= ids - {"product-0"}
                    count += 1
                    time.sleep(.02)
                return count

            with futures.ThreadPoolExecutor(max_workers=4) as pool:
                count = sum(pool.map(exercise, range(4)))
            assert health(b"", timeout=5) == b"\x08\x01"
            with lock:
                assert received == {"traces", "metrics", "logs"}, received
                assert flag_calls >= count, f"flagd v1 evaluations missing: {flag_calls}/{count}"
            state = json.loads(command("docker", "inspect", "--format", "{{json .State}}", name))
            assert state["Running"] and not state["OOMKilled"], state
            logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True, check=True)
            assert "Overriding of current LoggerProvider" not in logs.stdout + logs.stderr
            print(f"recommendation: {count} requests in {seconds}s; health and OTLP traces/metrics/logs passed")
        finally:
            if channel:
                channel.close()
            subprocess.run(["docker", "logs", "--tail", "15", name], check=False)
            subprocess.run(["docker", "rm", "-f", name], check=False, stdout=subprocess.DEVNULL)
            stop.set()
            backend.stop(0).wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error("--seconds must be positive")
    main(args.image, args.seconds)

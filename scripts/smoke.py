#!/usr/bin/env python3
"""Exercise a real local image over gRPC; always remove the test container."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from concurrent import futures
import threading
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
import grpc
from grpc_tools import protoc

ROOT = Path(__file__).resolve().parents[1]

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def main(service, image):
    with tempfile.TemporaryDirectory() as generated:
        assert protoc.main(['protoc', f'-I{ROOT / "pb"}', f'--python_out={generated}',
                            f'--grpc_python_out={generated}', str(ROOT / 'pb/demo.proto')]) == 0
        sys.path.insert(0, generated)
        import demo_pb2 as pb
        import demo_pb2_grpc as rpc
        received = set()
        lock = threading.Lock()
        collector = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        for signal, api in [('traces', 'trace'), ('metrics', 'metrics'), ('logs', 'logs')]:
            def export(payload, context, signal=signal):
                if service.encode() in payload:
                    with lock:
                        received.add(signal)
                return b''
            collector.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(
                f'opentelemetry.proto.collector.{api}.v1.{api.capitalize()}Service',
                {'Export': grpc.unary_unary_rpc_method_handler(export)}),))
        collector_port = collector.add_insecure_port('0.0.0.0:0')
        collector.start()
        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = self.rfile.read(int(self.headers['Content-Length']))
                if service.encode() in payload:
                    with lock:
                        received.add(self.path.rsplit('/', 1)[-1])
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-protobuf')
                self.send_header('Content-Length', '0')
                self.end_headers()
            def log_message(self, *args):
                pass
        http = ThreadingHTTPServer(('0.0.0.0', 0), Receiver)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        if service == 'ad':
            collector_port = http.server_port
        name = 'otel-smoke-'  + uuid.uuid4().hex[:12]
        args = ['docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::8080',
                '-e', f'{service.upper().replace("-", "_")}_PORT=8080',
                '-e', 'OTEL_SERVICE_NAME=' + service,
                '--add-host', 'host.docker.internal:host-gateway',
                '-e', f'OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:{collector_port}',
                '-e', 'OTEL_EXPORTER_OTLP_PROTOCOL=' + ('http/protobuf' if service == 'ad' else 'grpc'),
                '-e', 'OTEL_METRIC_EXPORT_INTERVAL=1000',
                '-e', 'FLAGD_HOST=localhost', '-e', 'FLAGD_PORT=8013']
        if service == 'product-catalog':
            args += ['--memory=' + os.getenv('SMOKE_MEMORY_LIMIT', '20m'), '-e', 'GOMEMLIMIT=16MiB', '-v', f'{ROOT / "tests/fixtures"}:/usr/src/app/products:ro']
        else:
            args += ['--memory=' + os.getenv('SMOKE_MEMORY_LIMIT', '300m')]
        args += [image]
        try:
            run(*args)
            port = run('docker', 'port', name, '8080/tcp').rsplit(':', 1)[1]
            channel = grpc.insecure_channel('127.0.0.1:' + port)
            grpc.channel_ready_future(channel).result(timeout=90)
            if service == 'product-catalog':
                client = rpc.ProductCatalogServiceStub(channel)
                expected = json.loads((ROOT / 'tests/fixtures/products.json').read_text())['products']
                products = client.ListProducts(pb.Empty(), timeout=10).products
                assert {p.id for p in products} == {p['id'] for p in expected}
                first = client.GetProduct(pb.GetProductRequest(id=expected[0]['id']), timeout=10)
                assert first.name == expected[0]['name']
                assert first.price_usd.units == expected[0]['priceUsd']['units']
                found = client.SearchProducts(pb.SearchProductsRequest(query=first.name.upper()), timeout=10)
                assert first.id in {p.id for p in found.results}
                try:
                    client.GetProduct(pb.GetProductRequest(id='missing'), timeout=10)
                    raise AssertionError('missing product succeeded')
                except grpc.RpcError as error:
                    assert error.code() == grpc.StatusCode.NOT_FOUND
                assert not client.SearchProducts(pb.SearchProductsRequest(query='no-match-xyz'), timeout=10).results
            else:
                client = rpc.AdServiceStub(channel)
                for keys in ([], ['telescopes']):
                    response = client.GetAds(pb.AdRequest(context_keys=keys), timeout=10)
                    assert response.ads and all(ad.text and ad.redirect_url for ad in response.ads)
            # gRPC health protocol: empty request checks overall server; SERVING = 1.
            health = channel.unary_unary('/grpc.health.v1.Health/Check')
            assert health(b'', timeout=10) == b'\x08\x01'
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with lock:
                    if received == {'traces', 'metrics', 'logs'}:
                        break
                time.sleep(0.2)
            assert received == {'traces', 'metrics', 'logs'}, f'missing telemetry signals: {received}'
            print(f'{service}: container gRPC, health, and OTLP traces/metrics/logs passed')
        finally:
            collector.stop(0)
            http.shutdown()
            subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', name], check=False)
            subprocess.run(['docker', 'logs', '--tail', '20', name], check=False)
            subprocess.run(['docker', 'rm', '-f', name], check=False, stdout=subprocess.DEVNULL)

if __name__ == '__main__':
    main(*sys.argv[1:])

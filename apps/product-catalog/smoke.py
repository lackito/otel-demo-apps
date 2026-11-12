#!/usr/bin/env python3
"""Exercise the catalog against a disposable PostgreSQL database and OTLP receiver."""
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

ROOT = Path(__file__).resolve().parents[2]

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def main(image):
    service = "product-catalog"
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
        name = 'otel-smoke-' + uuid.uuid4().hex[:12]
        args = ['docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::8080',
                '-e', f'{service.upper().replace("-", "_")}_PORT=8080',
                '-e', 'OTEL_SERVICE_NAME=' + service,
                '--add-host', 'host.docker.internal:host-gateway',
                '-e', f'OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:{collector_port}',
                '-e', 'OTEL_EXPORTER_OTLP_PROTOCOL=grpc',
                '-e', 'OTEL_METRIC_EXPORT_INTERVAL=1000',
                '-e', 'FLAGD_HOST=localhost', '-e', 'FLAGD_PORT=8013']
        database = name + '-db'
        args += ['--memory=' + os.getenv('SMOKE_MEMORY_LIMIT', '32m'), '-e', 'GOMEMLIMIT=16MiB', '--network', name, '-e', f'DB_CONNECTION_STRING=postgres://astronomy_user:smoke@{database}/astronomy_db?sslmode=disable']
        args += [image]
        try:
            run('docker', 'network', 'create', name)
            run('docker', 'run', '-d', '--network', name, '--name', database,
                '-e', 'POSTGRES_USER=astronomy_user', '-e', 'POSTGRES_PASSWORD=smoke',
                '-e', 'POSTGRES_DB=astronomy_db', 'postgres:18.4')
            psql = ['docker', 'exec', '-i', database, 'psql', '-XAt', '-v', 'ON_ERROR_STOP=1',
                    '-h', 'localhost', '-U', 'astronomy_user', '-d', 'astronomy_db']
            for _ in range(90):
                if subprocess.run(psql + ['-c', 'SELECT 1'], capture_output=True).returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('PostgreSQL did not become ready within 90 seconds')
            with (ROOT / 'apps/product-catalog/test-catalog.sql').open() as seed:
                subprocess.run(psql, stdin=seed, check=True)
            run(*args)
            port = run('docker', 'port', name, '8080/tcp').rsplit(':', 1)[1]
            channel = grpc.insecure_channel('127.0.0.1:' + port)
            grpc.channel_ready_future(channel).result(timeout=90)
            client = rpc.ProductCatalogServiceStub(channel)
            expected = json.loads((ROOT / 'tests/fixtures/products.json').read_text())['products']
            products = client.ListProducts(pb.Empty(), timeout=10).products
            assert {p.id for p in products} == set(run(*psql, '-c', 'SELECT id FROM catalog.products').splitlines())
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
            run(*psql, '-c', "UPDATE catalog.products SET name='Live database change' WHERE id='OLJCESPC7Z'")
            assert client.GetProduct(pb.GetProductRequest(id='OLJCESPC7Z'), timeout=10).name == 'Live database change'
            assert not client.SearchProducts(pb.SearchProductsRequest(query='no-match-xyz'), timeout=10).results
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
            subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', name], check=False)
            subprocess.run(['docker', 'logs', '--tail', '20', name], check=False)
            subprocess.run(['docker', 'rm', '-f', name], check=False, stdout=subprocess.DEVNULL)

            subprocess.run(['docker', 'rm', '-fv', database], check=False)
            subprocess.run(['docker', 'network', 'rm', name], check=False)

if __name__ == '__main__':
    main(sys.argv[1])

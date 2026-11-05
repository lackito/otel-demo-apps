#!/usr/bin/env python3
"""Render exact chart 0.38.4 with isolated candidate values, never active desired state."""
from pathlib import Path
import subprocess
import tempfile
from ruamel.yaml import YAML

with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(['helm', 'pull', 'opentelemetry-demo', '--repo',
                    'https://open-telemetry.github.io/opentelemetry-helm-charts',
                    '--version', '0.38.4', '--untar', '--untardir', tmp], check=True)
    chart = Path(tmp) / 'opentelemetry-demo'
    yaml = YAML(typ='safe')
    assert yaml.load((chart/'Chart.yaml').read_text())['version'] == '0.38.4'
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/products.json'
    assert fixture.read_bytes() == (chart/'products/products.json').read_bytes()
    args = ['helm', 'template', 'otel-demo', str(chart)]
    for service in ('product-catalog', 'ad'):
        args += ['--set-string', f'components.{service}.imageOverride.repository=example.invalid/{service}',
                 '--set-string', f'components.{service}.imageOverride.tag=' + 'a'*40]
    docs = list(yaml.load_all(subprocess.check_output(args, text=True)))
    deployments = {d['metadata']['name']:d for d in docs if d and d['kind']=='Deployment'}
    for service in ('product-catalog', 'ad'):
        deployment = next(d for name,d in deployments.items() if name.endswith(service))
        container = deployment['spec']['template']['spec']['containers'][0]
        assert container['image'] == f'example.invalid/{service}:' + 'a'*40
        env = {e['name']:e.get('value') for e in container['env']}
        assert env[service.upper().replace('-','_')+'_PORT'] == '8080'
        assert 'OTEL_EXPORTER_OTLP_ENDPOINT' in env
        if service == 'product-catalog':
            assert any(v['mountPath']=='/usr/src/app/products' for v in container['volumeMounts'])
            assert env['PRODUCT_CATALOG_RELOAD_INTERVAL']=='10'
    print('Chart 0.38.4: candidate images, ports, catalog mount, fixture, and telemetry environment verified')

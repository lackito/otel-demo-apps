import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from ruamel.yaml import YAML

spec = importlib.util.spec_from_file_location('promote', Path(__file__).parents[1] / 'scripts/promote.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class PromotionTests(unittest.TestCase):
    def test_aws_push_race_preserves_both_promotions(self):
        self.check_push_race('aws')

    def test_kind_push_race_preserves_both_promotions(self):
        self.check_push_race('kind')

    def check_push_race(self, target):
        def repository(service):
            if target == 'kind':
                return 'ghcr.io/lackito/otel-demo-kind-' + service
            return '123456789012.dkr.ecr.us-east-1.amazonaws.com/' + service
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            remote = root / 'remote.git'
            subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(remote)], check=True, capture_output=True)
            first, second = root / 'first', root / 'second'
            subprocess.run(['git', 'clone', str(remote), str(first)], check=True, capture_output=True)
            file = 'values.yaml'
            (first / file).write_text('# keep comment\ncomponents:\n  recommendation:\n    enabled: true\n    imageOverride:\n      repository: old\n      tag: old\n  ad:\n    env: []\n')
            p.git(first, 'add', '.')
            p.git(first, '-c', 'user.name=test', '-c', 'user.email=test@example.com', 'commit', '-m', 'initial')
            p.git(first, 'push', 'origin', 'main')
            subprocess.run(['git', 'clone', str(remote), str(second)], check=True, capture_output=True)
            real_git = p.git
            raced = False
            def racing_git(cwd, *args, **kwargs):
                nonlocal raced
                if Path(cwd) == first and args[0] == 'push' and not raced:
                    raced = True
                    p.promote(second, file, 'ad', repository('ad'), 'a'*40, target=target)
                return real_git(cwd, *args, **kwargs)
            with patch.object(p, 'git', racing_git), patch.object(p.time, 'sleep'):
                p.promote(first, file, 'product-catalog', repository('product-catalog'), 'b'*40, target=target)
            self.assertTrue(raced)
            result = YAML().load((first/file).read_text())['components']
            self.assertEqual(result['ad']['imageOverride']['tag'], 'a'*40)
            self.assertEqual(result['product-catalog']['imageOverride']['tag'], 'b'*40)
            self.assertEqual(result['recommendation']['imageOverride']['tag'], 'old')
            self.assertTrue(result['recommendation']['enabled'])
            self.assertEqual(result['ad']['env'], [])
            if target == 'kind':
                self.assertEqual(result['ad']['imageOverride']['pullPolicy'], 'IfNotPresent')
                self.assertEqual(result['product-catalog']['imageOverride']['pullPolicy'], 'IfNotPresent')
            self.assertIn('# keep comment', (first/file).read_text())
            head = p.git(first, 'rev-parse', 'HEAD').stdout
            p.promote(first, file, 'product-catalog', repository('product-catalog'), 'b'*40, target=target)
            self.assertEqual(head, p.git(first, 'rev-parse', 'HEAD').stdout)

    def test_kind_recommendation_and_pull_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'values.yaml'
            path.write_text('components:\n  recommendation:\n    env: []\n    imageOverride:\n      pullPolicy: Never\n  ad:\n    enabled: true\n')
            p.update(path, 'recommendation', 'ghcr.io/lackito/otel-demo-kind-recommendation', 'c'*40, target='kind')
            components = YAML().load(path.read_text())['components']
            self.assertEqual(components['recommendation']['imageOverride']['pullPolicy'], 'IfNotPresent')
            self.assertEqual(components['recommendation']['imageOverride']['tag'], 'c'*40)
            self.assertEqual(components['recommendation']['env'], [])
            self.assertTrue(components['ad']['enabled'])

    def test_target_and_component_registry_boundaries(self):
        for target, repository in [
            ('aws', 'ghcr.io/lackito/otel-demo-kind-ad'),
            ('kind', '123456789012.dkr.ecr.us-east-1.amazonaws.com/ad'),
            ('kind', 'ghcr.io/lackito/otel-demo-kind-product-catalog'),
            ('kind', 'ghcr.io/lackito/other-ad'),
        ]:
            with self.subTest(target=target, repository=repository), self.assertRaises(ValueError):
                p.update(Path('/unused'), 'ad', repository, 'a'*40, target=target)

    def test_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            p.update(Path('/unused'), 'ad', 'wrong-repository', 'a'*40)
        with self.assertRaises(ValueError):
            p.update(Path('/unused'), 'ad', '123456789012.dkr.ecr.us-east-1.amazonaws.com/ad', 'latest')

if __name__ == '__main__':
    unittest.main()

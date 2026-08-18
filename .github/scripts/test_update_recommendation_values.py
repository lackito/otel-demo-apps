from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from update_recommendation_values import update_values


VALUES = """\
components:
  recommendation:
    imageOverride:
      repository: otel-demo/recommendation
      tag: local-123456789012
      pullPolicy: IfNotPresent

  flagd:
    enabled: true
"""


class UpdateRecommendationValuesTest(TestCase):
    def test_updates_only_the_recommendation_image(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "values.yaml"
            path.write_text(VALUES, encoding="utf-8")

            update_values(
                path,
                "ghcr.io/lackito/otel-demo-local-recommendation",
                "1234567890abcdef1234567890abcdef12345678",
            )

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                VALUES.replace(
                    "otel-demo/recommendation",
                    "ghcr.io/lackito/otel-demo-local-recommendation",
                ).replace(
                    "local-123456789012",
                    "1234567890abcdef1234567890abcdef12345678",
                ),
            )

    def test_rejects_a_mutable_tag(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "values.yaml"
            path.write_text(VALUES, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "40-character Git SHA"):
                update_values(path, "ghcr.io/lackito/image", "latest")

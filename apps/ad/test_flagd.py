"""Run against a built Ad image and the real flagd version in chart 0.38.4."""
import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import grpc


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def write_flags(directory, high_cpu):
    flags = {
        key: {"state": "ENABLED", "variants": {"on": True, "off": False},
              "defaultVariant": "on" if key == "adHighCpu" and high_cpu else "off"}
        for key in ("adHighCpu", "adFailure", "adManualGc")
    }
    pending = directory / "pending"
    pending.write_text(json.dumps({"flags": flags}))
    pending.replace(directory / "flags.json")


def check(image):
    suffix = uuid.uuid4().hex[:12]
    flagd, ad = "flagd-test-" + suffix, "ad-test-" + suffix
    enabled_message = "High CPU-Load problempattern enabled"
    # Under the checkout so local Docker VMs can mount it as well as CI runners.
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
        directory = Path(tmp)
        directory.chmod(0o755)
        write_flags(directory, False)
        try:
            # Ad shares this isolated network namespace: localhost:8013 is flagd.
            docker("run", "-d", "--name", flagd, "-p", "127.0.0.1::8080",
                   "-v", f"{directory}:/flags:ro", "ghcr.io/open-feature/flagd:v0.12.8",
                   "start", "--uri", "file:/flags/flags.json")
            docker("run", "-d", "--name", ad, "--network", "container:" + flagd,
                   "--cpus=1", "-e", "AD_PORT=8080", "-e", "FLAGD_HOST=localhost",
                   "-e", "FLAGD_PORT=8013", "-e", "OTEL_TRACES_EXPORTER=none",
                   "-e", "OTEL_METRICS_EXPORTER=none", "-e", "OTEL_LOGS_EXPORTER=none", image)
            address = docker("port", flagd, "8080/tcp")
            with grpc.insecure_channel(address) as channel:
                grpc.channel_ready_future(channel).result(timeout=90)
                get_ads = channel.unary_unary("/oteldemo.AdService/GetAds")
                assert get_ads(b"", timeout=10), "Ad returned no ads"
                assert enabled_message not in docker("logs", ad)
                write_flags(directory, True)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    get_ads(b"", timeout=10)
                    if enabled_message in docker("logs", ad):
                        print("Ad observed adHighCpu change from off to on via flagd v0.12.8.")
                        return
                    time.sleep(0.5)
                raise AssertionError("Ad never acted on adHighCpu=true; check the flagd RPC version")
        finally:
            subprocess.run(["docker", "rm", "-f", ad, flagd], check=False,
                           stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    check(sys.argv[1])

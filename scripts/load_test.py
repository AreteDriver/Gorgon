#!/usr/bin/env python3
"""Load test script for the Gorgon API.

Uses only Python standard library (asyncio + urllib) for zero external dependencies.
Runs concurrent requests against health, auth, workflow, and template endpoints
and reports latency statistics.

Usage:
    python scripts/load_test.py
    python scripts/load_test.py --concurrency 20 --duration 60
    python scripts/load_test.py --url http://staging:8000
"""

import argparse
import asyncio
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RequestResult:
    """Result of a single HTTP request."""

    endpoint: str
    status: int
    latency: float  # seconds
    error: Optional[str] = None


@dataclass
class EndpointStats:
    """Aggregated stats for one endpoint."""

    name: str
    total: int = 0
    successes: int = 0
    failures: int = 0
    latencies: list = field(default_factory=list)


def make_request(
    method: str,
    url: str,
    endpoint: str,
    headers: Optional[dict] = None,
    body: Optional[bytes] = None,
) -> RequestResult:
    """Make a single HTTP request and return the result."""
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=body)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            latency = time.monotonic() - start
            return RequestResult(endpoint=endpoint, status=resp.status, latency=latency)
    except urllib.error.HTTPError as e:
        latency = time.monotonic() - start
        return RequestResult(
            endpoint=endpoint, status=e.code, latency=latency, error=str(e)
        )
    except Exception as e:
        latency = time.monotonic() - start
        return RequestResult(endpoint=endpoint, status=0, latency=latency, error=str(e))


def get_auth_token(base_url: str) -> Optional[str]:
    """Obtain a bearer token using demo credentials."""
    payload = json.dumps({"user_id": "loadtest", "password": "demo"}).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=payload,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("access_token")
    except Exception as e:
        print(f"[WARN] Could not obtain auth token: {e}")
        print("       Authenticated endpoints will be skipped.")
        return None


def build_test_plan(base_url: str, token: Optional[str]) -> list:
    """Build the list of (method, url, endpoint_name, headers, body) tuples."""
    plan = []

    # Health checks (no auth)
    for path in ["/health", "/health/live", "/health/ready"]:
        plan.append(("GET", f"{base_url}{path}", f"GET {path}", {}, None))

    # Authenticated endpoints
    if token:
        auth_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        plan.append(
            ("GET", f"{base_url}/v1/workflows", "GET /v1/workflows", auth_headers, None)
        )
        plan.append(
            ("GET", f"{base_url}/v1/prompts", "GET /v1/prompts", auth_headers, None)
        )

    # Auth login (rate-limited to 5/min so we include it but at low weight)
    login_body = json.dumps({"user_id": "loadtest", "password": "demo"}).encode()
    plan.append(
        (
            "POST",
            f"{base_url}/v1/auth/login",
            "POST /v1/auth/login",
            {"Content-Type": "application/json"},
            login_body,
        )
    )

    return plan


async def run_load_test(
    base_url: str,
    concurrency: int,
    duration: int,
) -> dict[str, EndpointStats]:
    """Run the load test and return per-endpoint stats."""
    token = get_auth_token(base_url)
    plan = build_test_plan(base_url, token)

    if not plan:
        print("No endpoints to test.")
        return {}

    stats: dict[str, EndpointStats] = {}
    for entry in plan:
        name = entry[2]
        if name not in stats:
            stats[name] = EndpointStats(name=name)

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=concurrency)
    stop_event = asyncio.Event()
    idx = 0

    async def worker() -> None:
        nonlocal idx
        while not stop_event.is_set():
            entry = plan[idx % len(plan)]
            idx += 1
            method, url, name, headers, body = entry
            result = await loop.run_in_executor(
                executor, make_request, method, url, name, headers, body
            )
            ep = stats[name]
            ep.total += 1
            ep.latencies.append(result.latency)
            if 200 <= result.status < 400:
                ep.successes += 1
            else:
                ep.failures += 1

    print(f"Load test: {concurrency} workers, {duration}s duration, target={base_url}")
    print(f"Endpoints: {', '.join(s.name for s in stats.values())}")
    print("-" * 70)

    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]

    await asyncio.sleep(duration)
    stop_event.set()

    await asyncio.gather(*workers)
    executor.shutdown(wait=False)

    return stats


def percentile(data: list[float], p: float) -> float:
    """Compute the p-th percentile (0-100) of a sorted list."""
    if not data:
        return 0.0
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(data) else f
    d = k - f
    return data[f] + d * (data[c] - data[f])


def print_report(stats: dict[str, EndpointStats], duration: int) -> None:
    """Print the summary report."""
    total_req = sum(s.total for s in stats.values())
    total_ok = sum(s.successes for s in stats.values())
    total_fail = sum(s.failures for s in stats.values())
    all_latencies = sorted(lat for s in stats.values() for lat in s.latencies)

    print()
    print("=" * 70)
    print("LOAD TEST REPORT")
    print("=" * 70)
    print(f"Duration:       {duration}s")
    print(f"Total requests: {total_req}")
    print(f"Successes:      {total_ok}")
    print(f"Failures:       {total_fail}")
    print(f"Requests/sec:   {total_req / duration:.1f}")
    print()

    if all_latencies:
        print("Overall Latency:")
        print(f"  avg:  {statistics.mean(all_latencies) * 1000:.1f} ms")
        print(f"  p50:  {percentile(all_latencies, 50) * 1000:.1f} ms")
        print(f"  p95:  {percentile(all_latencies, 95) * 1000:.1f} ms")
        print(f"  p99:  {percentile(all_latencies, 99) * 1000:.1f} ms")
        print()

    print(
        f"{'Endpoint':<30} {'Total':>7} {'OK':>7} {'Fail':>7} {'Avg(ms)':>9} {'p95(ms)':>9}"
    )
    print("-" * 70)
    for ep in stats.values():
        if not ep.latencies:
            continue
        sorted_lat = sorted(ep.latencies)
        avg = statistics.mean(sorted_lat) * 1000
        p95 = percentile(sorted_lat, 95) * 1000
        print(
            f"{ep.name:<30} {ep.total:>7} {ep.successes:>7} "
            f"{ep.failures:>7} {avg:>9.1f} {p95:>9.1f}"
        )
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test for Gorgon API")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent workers (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds (default: 30)",
    )
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    stats = asyncio.run(run_load_test(base_url, args.concurrency, args.duration))
    print_report(stats, args.duration)


if __name__ == "__main__":
    main()

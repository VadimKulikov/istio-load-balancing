#!/usr/bin/env python3
"""
Test request distribution across pods in Kubernetes.
Sends requests in bulk and displays distribution statistics.
"""

import requests
import concurrent.futures
import sys
from collections import Counter
from urllib.parse import urlparse
import argparse
import time

def make_request(session, url, timeout=10):
    """Make a single request and return the pod name. Reuses TCP connection via session."""
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        return f"ERROR: {type(e).__name__}"

def make_request_with_delay(session, url, delay_ms, timeout=10):
    """Wait for the specified delay, then make a request."""
    time.sleep(delay_ms / 1000.0)
    return make_request(session, url, timeout)

def run_batch(url, batch_size):
    """Send bulk requests in parallel with 10ms delay between starts."""
    print(f"  Batch: sending {batch_size} requests in parallel (10ms stagger between starts, reusing TCP connections)...", flush=True)
    
    start_time = time.time()
    
    # Create a session to reuse TCP connections
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=batch_size, pool_maxsize=batch_size)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # Submit all requests to thread pool with 10ms delay between each submission
    with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = []
        for i in range(batch_size):
            # Each request starts 10ms after the previous one
            future = executor.submit(make_request_with_delay, session, url, i * 3, 10)
            futures.append(future)
        
        # Collect all results as they complete
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    session.close()
    duration = time.time() - start_time
    
    # Filter out errors
    successful = [r for r in results if not r.startswith("ERROR:")]
    errors = batch_size - len(successful)
    
    return {
        'results': successful,
        'errors': errors,
        'duration': duration,
        'batch_size': batch_size
    }

def display_aggregate_report(batch_results):
    """Display aggregated report from all batches."""
    if not batch_results:
        print("No results to display.")
        return
    
    # Aggregate data across all batches
    all_results = []
    total_errors = 0
    total_duration = 0
    total_requests = 0
    
    for batch in batch_results:
        all_results.extend(batch['results'])
        total_errors += batch['errors']
        total_duration += batch['duration']
        total_requests += batch['batch_size']
    
    # Count distribution
    counts = Counter(all_results)
    total_successful = len(all_results)
    unique_pods = len(counts)
    num_batches = len(batch_results)
    
    avg_duration = total_duration / num_batches
    
    # Print aggregated results
    print("\n" + "=" * 60)
    print("           AGGREGATED REPORT (All Batches)")
    print("=" * 60)
    print(f"Total Batches: {num_batches}")
    print(f"Total Requests: {total_requests}")
    print(f"Successful: {total_successful}")
    print(f"Failed: {total_errors}")
    print(f"Unique Pods Used: {unique_pods}")
    print(f"Avg Duration per Batch: {avg_duration:.2f}s")
    print(f"Overall RPS: {total_requests/total_duration:.1f}")
    print("-" * 60)
    print(f"{'Pod Name':<30} {'Count':<8} {'Percentage':<10}")
    print("-" * 60)
    
    # Sort by count descending
    for pod, count in counts.most_common():
        percentage = (count / total_successful) * 100
        bar = "█" * int(percentage / 5)  # Visual bar chart
        print(f"{pod:<30} {count:<8} {percentage:>6.1f}% {bar}")
    
    print("-" * 60)
    
    # Check distribution evenness
    if unique_pods > 1:
        expected = total_successful / 10
        variance = sum((count - expected) ** 2 for count in counts.values()) / unique_pods
        std_dev = variance ** 0.5
        print(f"Expected per pod: {expected:.1f}")
        print(f"Std Deviation: {std_dev:.2f} ({(std_dev/expected)*100:.1f}%)")
        
        if std_dev / expected > 0.3:
            print("⚠️  Distribution appears uneven (>30% variance)")
        else:
            print("✅ Distribution appears even")
    else:
        print("⚠️  Only 1 pod handled all requests!")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test K8s request distribution')
    parser.add_argument('--url', '-u', default='http://192.168.49.2:30914',
                       help='Target URL (default: http://192.168.49.2)')
    parser.add_argument('--count', '-n', type=int, default=40,
                       help='Number of requests per batch (default: 100)')
    parser.add_argument('--batches', '-b', type=int, default=2,
                       help='Number of batches to run (default: 1)')
    
    args = parser.parse_args()
    
    # Verify URL is reachable first
    try:
        r = requests.get(args.url, timeout=5)
        print(f"✅ Target reachable: {args.url}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot reach {args.url}: {e}")
        print("💡 Tip: If running inside cluster, use http://192.168.49.2")
        sys.exit(1)
    
    # Run batches and collect results
    batch_results = []
    print(f"\nRunning {args.batches} batch(es) of {args.count} requests each...")
    print()
    
    for i in range(args.batches):
        if args.batches > 1:
            print(f"[Batch {i+1}/{args.batches}]")
        result = run_batch(args.url, args.count)
        batch_results.append(result)
        if i < args.batches - 1:
            time.sleep(1)  # Brief pause between batches
    
    # Display aggregated report after all batches complete
    display_aggregate_report(batch_results)

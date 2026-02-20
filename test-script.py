#!/usr/bin/env python3

import requests
import concurrent.futures
import sys
from collections import Counter
from urllib.parse import urlparse
import argparse
import time

def make_request(session, url, delay_ms, timeout=10):
    time.sleep(delay_ms / 1000.0)

    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        return f"ERROR: {type(e).__name__}"

def run_batch(url, batch_size):
    start_time = time.time()
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=batch_size, pool_maxsize=batch_size)
    session.mount('http://', adapter)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = []
        for i in range(batch_size):
            future = executor.submit(make_request, session, url, i * 5, 10)
            futures.append(future)
        
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    session.close()
    duration = time.time() - start_time
    
    successful = [r for r in results if not r.startswith("ERROR:")]
    errors = batch_size - len(successful)
    
    return {
        'results': successful,
        'errors': errors,
        'duration': duration,
        'batch_size': batch_size
    }

def display_aggregate_report(batch_results, batch_size):
    all_results = []
    total_errors = 0
    total_duration = 0
    total_requests = 0
    
    for batch in batch_results:
        all_results.extend(batch['results'])
        total_errors += batch['errors']
        total_duration += batch['duration']
        total_requests += batch['batch_size']
    
    counts = Counter(all_results)
    total_successful = len(all_results)
    unique_pods = len(counts)
    num_batches = len(batch_results)
    
    avg_duration = total_duration / num_batches
    
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
    print(f"{'Pod Name':<30} {'Count':<8}")
    print("-" * 60)
    
    for pod, count in counts.most_common():
        percentage = (count / total_successful) * 100
        print(f"{pod:<30} {count:<8}")
    
    print("-" * 60)
    
    expected = total_successful / batch_size
    variance = sum((count - expected) ** 2 for count in counts.values()) / unique_pods
    std_dev = variance ** 0.5
    print(f"Expected per pod: {expected:.1f}")
    print(f"Std Deviation: {std_dev:.2f} ({(std_dev/expected)*100:.1f}%)")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', '-u', default='http://192.168.49.2:30914')
    parser.add_argument('--count', '-n', type=int, default=40)
    parser.add_argument('--batches', '-b', type=int, default=2,)
    
    args = parser.parse_args()
    
    try:
        r = requests.get(args.url, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot reach {args.url}: {e}")
        sys.exit(1)
    
    batch_results = []
    print(f"\nRunning {args.batches} batch(es) of {args.count} requests each...")
    print()
    
    for i in range(args.batches):
        if args.batches > 1:
            print(f"[Batch {i+1}/{args.batches}]")
        result = run_batch(args.url, args.count)
        batch_results.append(result)
        if i < args.batches - 1:
            time.sleep(5)
    
    display_aggregate_report(batch_results, args.count)

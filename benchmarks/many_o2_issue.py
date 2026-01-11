#!/usr/bin/env python3
"""
Benchmark to demonstrate O(n²) performance issue in many() and many1()

This script benchmarks parsing sequences of digits with increasing input sizes
to show the quadratic time complexity caused by list concatenation.
"""

import time

from pyparsec import many1, digit, run_parser


def benchmark_many(n):
    """Benchmark parsing n digits with many1(digit())."""
    input_str = "1" * n

    start = time.perf_counter()
    result, err = run_parser(many1(digit()), input_str)
    elapsed = time.perf_counter() - start

    if err:
        print(f"Error parsing {n} items: {err}")
        return None

    if len(result) != n:
        print(f"Warning: Expected {n} items, got {len(result)}")

    return elapsed * 1000  # Convert to milliseconds


def main():
    print("=" * 70)
    print("PyParsec many() / many1() Performance Benchmark")
    print("=" * 70)
    print("\nDemonstrating O(n²) complexity due to list concatenation:")
    print("Code: lambda item, lst: lst + [item]  # Creates new list each time")
    print()
    print(
        f"{'Input (n)':>12} | {'Time (ms)':>12} | {'Time per item (µs)':>18} | {'Growth Factor':>15}"
    )
    print("-" * 70)

    prev_time = None
    prev_n = None

    for n in [1000, 2000, 4000, 8000, 16000]:
        elapsed = benchmark_many(n)

        if elapsed:
            time_per_item = elapsed * 1000 / n  # microseconds per item

            # Calculate growth factor
            if prev_time and prev_n:
                n_ratio = n / prev_n
                time_ratio = elapsed / prev_time
                expected_ratio = n_ratio * n_ratio  # Expected for O(n²)
                growth = (
                    f"{time_ratio:.1f}x (expected ~{expected_ratio:.1f}x for O(n²))"
                )
            else:
                growth = "baseline"

            print(
                f"{n:>12,} | {elapsed:>12.2f} | {time_per_item:>18.2f} | {growth:>15}"
            )

            prev_time = elapsed
            prev_n = n

    print()
    print("Analysis:")
    print("-" * 70)
    print("If time complexity is O(n):")
    print("  - Doubling input should roughly double time (growth ~2x)")
    print("  - Time per item should remain constant")
    print()
    print("If time complexity is O(n²):")
    print("  - Doubling input should roughly quadruple time (growth ~4x)")
    print("  - Time per item should grow linearly with input size")
    print()
    print("Current behavior shows O(n²) - this is the issue we need to fix.")
    print("=" * 70)


if __name__ == "__main__":
    main()

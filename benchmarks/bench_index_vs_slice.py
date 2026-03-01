"""
Benchmark: Zero-copy index-based parsing vs O(N²) input slicing.

Measures wall-clock time for parsing inputs of increasing size to
demonstrate the algorithmic complexity difference.

Usage:
    uv run python benchmarks/bench_index_vs_slice.py
"""

import timeit
from pyparsec.Char import char, string, digit, letter, alpha_num
from pyparsec.Prim import many, many1, run_parser
from pyparsec.Combinators import sep_by, choice


def bench_many_char(sizes: list[int], repeats: int = 5) -> dict[int, float]:
    """Benchmark many(char('a')) on strings of increasing size."""
    parser = many(char("a"))
    results = {}
    for n in sizes:
        data = "a" * n
        t = timeit.timeit(lambda: run_parser(parser, data), number=repeats)
        results[n] = t / repeats
    return results


def bench_string_match(sizes: list[int], repeats: int = 5) -> dict[int, float]:
    """Benchmark string() matching at the start of a large input."""
    results = {}
    for n in sizes:
        target = "hello"
        data = target + "x" * n
        parser = string(target)
        t = timeit.timeit(lambda: run_parser(parser, data), number=repeats)
        results[n] = t / repeats
    return results


def bench_many_digit(sizes: list[int], repeats: int = 5) -> dict[int, float]:
    """Benchmark many1(digit()) — simulates parsing a very large integer literal."""
    parser = many1(digit())
    results = {}
    for n in sizes:
        data = "1" * n
        t = timeit.timeit(lambda: run_parser(parser, data), number=repeats)
        results[n] = t / repeats
    return results


def bench_csv_line(sizes: list[int], repeats: int = 5) -> dict[int, float]:
    """Benchmark sep_by(many1(letter()), char(',')) — CSV-like field parsing."""
    parser = sep_by(many1(letter()), char(","))
    results = {}
    for n in sizes:
        # n fields of 5 letters each
        data = ",".join("abcde" for _ in range(n))
        t = timeit.timeit(lambda: run_parser(parser, data), number=repeats)
        results[n] = t / repeats
    return results


def bench_token_list(sizes: list[int], repeats: int = 5) -> dict[int, float]:
    """Benchmark parsing a list input (generic token stream)."""
    from pyparsec.Prim import token as prim_token
    from pyparsec.Parsec import SourcePos

    int_token = prim_token(
        show_tok=lambda t: str(t),
        test_tok=lambda t: t if isinstance(t, int) else None,
        next_pos=lambda pos, t: SourcePos(pos.line, pos.column + 1, pos.name),
    )
    parser = many(int_token)
    results = {}
    for n in sizes:
        data = list(range(n))
        t = timeit.timeit(lambda: run_parser(parser, data), number=repeats)
        results[n] = t / repeats
    return results


def format_time(seconds: float) -> str:
    if seconds < 1e-3:
        return f"{seconds * 1e6:8.1f} us"
    elif seconds < 1:
        return f"{seconds * 1e3:8.2f} ms"
    else:
        return f"{seconds:8.3f}  s"


def print_results(name: str, results: dict[int, float]) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")
    print(f"  {'Size':>10}  {'Time':>12}  {'Ratio vs smallest':>18}")
    print(f"  {'-'*10}  {'-'*12}  {'-'*18}")

    baseline = list(results.values())[0]
    for size, elapsed in results.items():
        ratio = elapsed / baseline if baseline > 0 else 0
        print(f"  {size:>10,}  {format_time(elapsed)}  {ratio:>17.1f}x")


def main() -> None:
    sizes = [1_000, 5_000, 10_000, 50_000, 100_000]
    csv_sizes = [200, 1_000, 5_000, 10_000, 20_000]

    print("PyParsec Parsing Benchmark")
    print("=" * 60)

    suites = [
        ("many(char('a'))", bench_many_char, sizes),
        ("many1(digit())", bench_many_digit, sizes),
        ("sep_by (CSV-like)", bench_csv_line, csv_sizes),
        ("string() match", bench_string_match, sizes),
        ("List[int] tokens", bench_token_list, sizes),
    ]

    for name, fn, sz in suites:
        results = fn(sz)
        print_results(name, results)

    print()


if __name__ == "__main__":
    main()

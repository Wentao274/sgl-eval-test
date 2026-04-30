"""``sgl-eval`` CLI entry point.

Three subcommands:
  list                 enumerate registered benchmarks
  ping                 send one chat completion to the endpoint and print it
  run <name>           run a benchmark end-to-end (filled in as benchmarks land)
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from sgl_eval.metrics import dump_run, format_summary
from sgl_eval.registry import get, list_evals
from sgl_eval.sampler import ChatCompletionSampler
from sgl_eval.types import GenConfig


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="sgl-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list registered benchmarks")
    p_list.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show per-benchmark defaults (sampling params, n_repeats, thinking)",
    )
    p_list.set_defaults(func=cmd_list)

    p_ping = sub.add_parser("ping", help="send one request to the endpoint")
    _add_endpoint_args(p_ping)
    p_ping.add_argument("--prompt", default="Reply with the single word: pong.")
    p_ping.add_argument("--max-tokens", type=int, default=64)
    p_ping.add_argument("--temperature", type=float, default=0.0)
    p_ping.set_defaults(func=cmd_ping)

    p_run = sub.add_parser("run", help="run a benchmark")
    p_run.add_argument("name", help="benchmark name (see `sgl-eval list`)")
    _add_endpoint_args(p_run)
    p_run.add_argument("--num-examples", type=int, default=None)
    p_run.add_argument("--num-threads", type=int, default=64)
    p_run.add_argument("--n-repeats", type=int, default=None)
    p_run.add_argument("--max-tokens", type=int, default=None)
    p_run.add_argument("--temperature", type=float, default=None)
    p_run.add_argument("--top-p", type=float, default=None)
    p_run.add_argument(
        "--thinking",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="override chat_template_kwargs.thinking (per-benchmark default applies otherwise)",
    )
    p_run.add_argument("--out-dir", default=None)
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


def _add_endpoint_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--base-url", required=True, help="OpenAI-compatible endpoint, e.g. http://host:30000/v1"
    )
    p.add_argument("--model", default=None, help="model id (defaults to first /v1/models entry)")
    p.add_argument("--api-key", default="EMPTY")


def cmd_list(args: argparse.Namespace) -> int:
    specs = list_evals()
    if not specs:
        print("(no benchmarks registered yet)")
        return 0
    if args.verbose:
        for s in specs:
            gen = s.default_gen
            ctk = gen.chat_template_kwargs or {}
            thinking = bool(ctk.get("thinking"))
            print(f"\n{s.name}  [{s.category}]")
            print(f"  description : {s.description}")
            print(f"  n_repeats   : {s.default_n_repeats}")
            print(f"  thinking    : {thinking}")
            print(f"  temperature : {gen.temperature}")
            print(f"  top_p       : {gen.top_p}")
            print(f"  max_tokens  : {gen.max_tokens}")
        return 0
    width = max(len(s.name) for s in specs)
    for s in specs:
        print(f"  {s.name:<{width}s}  [{s.category}]  {s.description}")
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    sampler = ChatCompletionSampler(base_url=args.base_url, model=args.model, api_key=args.api_key)
    gen = GenConfig(temperature=args.temperature, max_tokens=args.max_tokens)
    sample = sampler([{"role": "user", "content": args.prompt}], gen)
    print(f"model            : {sampler.model}")
    print(f"finish_reason    : {sample.finish_reason}")
    print(f"completion_tokens: {sample.completion_tokens}")
    print(f"prompt_tokens    : {sample.prompt_tokens}")
    print("--- response ---")
    print(sample.text)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    spec = get(args.name)
    sampler = ChatCompletionSampler(base_url=args.base_url, model=args.model, api_key=args.api_key)
    gen = _override_gen(spec.default_gen, args)
    n_repeats = args.n_repeats if args.n_repeats is not None else spec.default_n_repeats

    _warn_if_greedy_repeats(n_repeats, gen)

    result = spec.run(
        sampler=sampler,
        gen=gen,
        n_repeats=n_repeats,
        num_examples=args.num_examples,
        num_threads=args.num_threads,
    )
    print(format_summary(result))
    path = dump_run(result, args.out_dir)
    print(f"\nMetrics written to: {path}")
    return 0


def _override_gen(default: GenConfig, args: argparse.Namespace) -> GenConfig:
    chat_template_kwargs = dict(default.chat_template_kwargs or {})
    if args.thinking is not None:
        chat_template_kwargs["thinking"] = args.thinking
    return GenConfig(
        temperature=args.temperature if args.temperature is not None else default.temperature,
        top_p=args.top_p if args.top_p is not None else default.top_p,
        max_tokens=args.max_tokens if args.max_tokens is not None else default.max_tokens,
        reasoning_effort=default.reasoning_effort,
        chat_template_kwargs=chat_template_kwargs or None,
        extra_body=default.extra_body,
        seed=default.seed,
        system_message=default.system_message,
    )


def _warn_if_greedy_repeats(n_repeats: int, gen: GenConfig) -> None:
    if n_repeats > 1 and gen.temperature == 0.0:
        print(
            f"WARNING: n_repeats={n_repeats} but temperature=0.0 (greedy). "
            f"All {n_repeats} samples per example will be identical -- pass "
            "--temperature N (e.g. 1.0 for DSv3.2/V4, 0.6 for R1) for stochastic sampling.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())

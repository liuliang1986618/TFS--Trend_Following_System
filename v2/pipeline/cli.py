"""CLI parsing boundary for TFS v2."""

from __future__ import annotations

import argparse

from .runner import PipelineRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tfs-v2")
    subparsers = parser.add_subparsers(dest="command")

    daily = subparsers.add_parser("daily", help="run the daily v2 pipeline")
    daily.add_argument("--date", default=None)
    daily.add_argument("--max-candidates", type=int, default=50)
    daily.add_argument("--render", dest="render_display", action="store_true", default=True)
    daily.add_argument("--no-render", dest="render_display", action="store_false")
    daily.add_argument("--output-dir", default=None)
    daily.add_argument("--skip-health", action="store_true", default=False,
                       help="Skip data health check (for development/testing)")

    eval_cmd = subparsers.add_parser("eval", help="run pipeline through evaluation")
    eval_cmd.add_argument("--date", default=None)
    eval_cmd.add_argument("--max-candidates", type=int, default=50)
    eval_cmd.add_argument("--output-dir", default=None)
    eval_cmd.set_defaults(render_display=False)

    subparsers.add_parser("help", help="show help")
    parser.set_defaults(command="help")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "help":
        parser.print_help()
        return 0
    if args.command in ("daily", "eval"):
        runner = PipelineRunner(output_dir=args.output_dir, skip_health_check=getattr(args, "skip_health", False))
        manifest = runner.run(
            date=args.date,
            mode=args.command,
            render_display=getattr(args, "render_display", False),
            max_candidates=args.max_candidates,
        )
        return 0 if manifest.status == "success" else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

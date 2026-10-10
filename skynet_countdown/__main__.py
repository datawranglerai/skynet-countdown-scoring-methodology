"""Command-line entry point; collection and external output adapters are out of scope."""

import argparse
import sys
from pathlib import Path

from openai import OpenAI, OpenAIError

from .config import load_config
from .models import Dataset
from .pipeline import evaluate
from .scoring import remaining_seconds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate supplied Skynet Countdown stories.")
    parser.add_argument(
        "--input", type=Path, required=True, help="JSON object containing a stories array"
    )
    parser.add_argument("--output", type=Path, help="New local JSON output file")
    parser.add_argument(
        "--config", type=Path, default=Path("config.toml"), help="TOML settings file"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Validate inputs without API calls"
    )
    args = parser.parse_args(argv)
    if not args.validate_only and args.output is None:
        parser.error("--output is required unless --validate-only is used")
    try:
        config = load_config(args.config)
        dataset = Dataset.model_validate_json(args.input.read_text(encoding="utf-8-sig"))
        remaining_seconds(config.clock.initial_evidence_points, config.clock)
        if args.validate_only:
            print(
                f"Valid configuration and {len(dataset.stories)} unique story/stories. No API calls made."
            )
            return 0
        # Reserve the exact output path before any paid calls; never overwrite inputs or results.
        with args.output.open("x", encoding="utf-8") as output:
            try:
                with OpenAI(
                    timeout=config.request_timeout_seconds,
                    max_retries=config.api_max_retries,
                ) as client:
                    result = evaluate(dataset, config, client=client)
                output.write(result.model_dump_json(indent=2) + "\n")
            except BaseException:
                output.close()
                args.output.unlink(missing_ok=True)  # Only the file reserved above.
                raise
        assessed = sum(story.calculation is not None for story in result.stories)
        written = sum(story.report is not None for story in result.stories)
        errors = sum(story.error is not None for story in result.stories)
        print(f"Saved {args.output}: {assessed} assessed, {written} reports, {errors} errors.")
        return 0 if result.complete else 1
    except (OSError, ValueError, OpenAIError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

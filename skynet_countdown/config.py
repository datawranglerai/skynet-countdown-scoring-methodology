"""Configuration uses TOML, which Python can read without another dependency."""

import tomllib
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .models import EvidencePoints, NonnegativeInt, StrictModel, Text

PositiveInt = Annotated[int, Field(gt=0)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class ChainConfig(StrictModel):
    model: Text = "gpt-5.4"
    reasoning_effort: Literal[
        "omit", "none", "minimal", "low", "medium", "high", "xhigh", "max"
    ] = "high"
    max_iterations: PositiveInt = 2
    max_output_tokens: PositiveInt = 8192


class ScorerConfig(ChainConfig):
    web_search: bool = False
    web_search_context_size: Literal["low", "medium", "high"] = "medium"
    max_tool_calls: PositiveInt = 5


class SeverityThresholds(StrictModel):
    CANARY: PositiveInt = 1
    NOTABLE: PositiveInt = 3
    SIGNIFICANT: PositiveInt = 5
    CRITICAL: PositiveInt = 7
    EXISTENTIAL: PositiveInt = 13

    @model_validator(mode="after")
    def increasing_thresholds(self) -> Self:
        thresholds = list(self.model_dump().values())
        if thresholds[0] != 1 or any(a >= b for a, b in pairwise(thresholds)):
            raise ValueError("Severity thresholds must start at 1 and strictly increase.")
        return self


class ScoringConfig(StrictModel):
    trifecta_points: Annotated[list[NonnegativeInt], Field(min_length=4, max_length=4)] = Field(
        default_factory=lambda: [0, 1, 3, 7]
    )
    severity_thresholds: SeverityThresholds = Field(default_factory=SeverityThresholds)

    @model_validator(mode="after")
    def increasing_trifecta_points(self) -> Self:
        points = self.trifecta_points
        if points[0] != 0 or any(a > b for a, b in pairwise(points)):
            raise ValueError("Trifecta points must start at zero and never decrease.")
        return self


class ClockConfig(StrictModel):
    initial_seconds: PositiveFloat = 900.0
    half_scale_points: PositiveFloat = 1000.0
    initial_evidence_points: EvidencePoints = 0


class Config(StrictModel):
    minimum_relevance_score: Annotated[int, Field(ge=1, le=10)] = 2
    minimum_report_score: NonnegativeInt = 2
    write_reports: bool = True
    request_timeout_seconds: PositiveFloat = 180.0
    api_max_retries: NonnegativeInt = 2
    relevance: ChainConfig = Field(default_factory=ChainConfig)
    scorer: ScorerConfig = Field(default_factory=ScorerConfig)
    writer: ChainConfig = Field(default_factory=ChainConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    clock: ClockConfig = Field(default_factory=ClockConfig)


def load_config(path: str | Path) -> Config:
    with Path(path).open("rb") as handle:
        return Config.model_validate(tomllib.load(handle))

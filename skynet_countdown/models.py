"""Validated contracts for supplied stories, model judgements and Python results."""

from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Text = Annotated[str, Field(min_length=1)]
NonnegativeInt = Annotated[int, Field(ge=0)]
MAX_SAFE_EVIDENCE_POINTS = 2**53 - 1
EvidencePoints = Annotated[int, Field(ge=0, le=MAX_SAFE_EVIDENCE_POINTS)]
Severity = Literal["NO_MOVEMENT", "CANARY", "NOTABLE", "SIGNIFICANT", "CRITICAL", "EXISTENTIAL"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Story(StrictModel):
    id: Text
    title: Text
    source_url: HttpUrl
    published_date: date
    summary: Text
    content: Text | None = None
    reddit_post_url: HttpUrl | None = None
    subreddit: Text | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Dataset(StrictModel):
    stories: list[Story]

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        """Validate that every story has a distinct identifier.

        :return: The validated dataset.
        :rtype: Self
        :raises ValueError: If two or more stories have the same identifier.
        """
        ids = [story.id for story in self.stories]
        if len(ids) != len(set(ids)):
            raise ValueError("Story IDs must be unique; supply each event once.")
        return self


class Relevance(StrictModel):
    relevant_to_skynet: bool
    relevance_rationale: Text
    relevance_score: Annotated[int, Field(ge=1, le=10)]
    primary_dimension: Literal[
        "trifecta",
        "governance",
        "autonomy",
        "erosion",
        "sentience",
        "physical",
        "quantum",
        "none",
    ]

    @model_validator(mode="after")
    def low_scores_are_irrelevant(self) -> Self:
        """Require low relevance scores to be marked irrelevant.

        :return: The validated relevance assessment.
        :rtype: Self
        :raises ValueError: If a score of one or two is marked relevant.
        """
        if self.relevant_to_skynet and self.relevance_score <= 2:
            raise ValueError("Relevance scores 1–2 must be marked irrelevant under the rubric.")
        return self


class BinaryCriterion(StrictModel):
    score: Annotated[int, Field(ge=0, le=1)]
    rationale: Text


class AmplifierCriterion(StrictModel):
    score: Annotated[int, Field(ge=0, le=2)]
    rationale: Text


class Trifecta(StrictModel):
    t1: BinaryCriterion
    t2: BinaryCriterion
    t3: BinaryCriterion


class Amplifiers(StrictModel):
    governance_vacuum: AmplifierCriterion
    autonomy_without_oversight: AmplifierCriterion
    human_capability_erosion: AmplifierCriterion
    sentience_self_preservation: AmplifierCriterion
    physical_weaponisation: AmplifierCriterion


class Assessment(StrictModel):
    """LLM output: evidence judgements only, with no calculated fields."""

    trifecta: Trifecta
    amplifiers: Amplifiers
    is_leading_indicator: bool
    leading_indicator_note: str
    scoring_notes: str

    @model_validator(mode="after")
    def leading_indicator_has_explanation(self) -> Self:
        """Keep the leading-indicator flag and explanatory note consistent.

        :return: The validated assessment.
        :rtype: Self
        :raises ValueError: If the flag and presence of a note do not agree.
        """
        if self.is_leading_indicator != bool(self.leading_indicator_note):
            raise ValueError("Provide a leading_indicator_note exactly when the flag is true.")
        return self


class Editorial(StrictModel):
    """Writer output: factual account and interpretation are kept separate."""

    headline: Text
    metadata_line: Text
    the_story: Text
    our_take: Text

    @model_validator(mode="after")
    def headline_length(self) -> Self:
        """Limit the headline to twelve words.

        :return: The validated editorial content.
        :rtype: Self
        :raises ValueError: If the headline contains more than twelve words.
        """
        if len(self.headline.split()) > 12:
            raise ValueError("The headline must contain at most 12 words.")
        return self

    @model_validator(mode="after")
    def metadata_fragments(self) -> Self:
        """Require one lowercase metadata line with three fragments separated by ``' · '``.

        :return: The validated editorial content.
        :rtype: Self
        :raises ValueError: If there are not exactly three nonempty fragments, the
            text is not lowercase, or the line contains a newline or carriage return.
        """
        fragments = self.metadata_line.split(" · ")
        if (
            len(fragments) != 3
            or any(not fragment.strip() for fragment in fragments)
            or self.metadata_line != self.metadata_line.lower()
            or "\n" in self.metadata_line
            or "\r" in self.metadata_line
        ):
            raise ValueError("Metadata must be one lowercase line with three ' · ' fragments.")
        return self


class ClockMovement(StrictModel):
    cumulative_points_before: EvidencePoints
    cumulative_points_after: EvidencePoints
    remaining_seconds_before: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    remaining_seconds_after: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    delta_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    gap_closed_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class CalculatedScore(StrictModel):
    trifecta_active: Annotated[int, Field(ge=0, le=3)]
    full_trifecta: bool
    trifecta_points: NonnegativeInt
    amplifier_points: NonnegativeInt
    raw_source_total: NonnegativeInt
    total_score: NonnegativeInt
    max_score: Annotated[int, Field(gt=0)]
    classification: Severity
    clock: ClockMovement


class Report(Editorial):
    story_id: Text
    severity_label: Severity
    clock_delta_label: Text
    remaining_time: Text


class AgentRun(StrictModel):
    response_id: str
    model: str
    status: str
    usage: dict[str, Any] | None
    citations: list[dict[str, Any]]
    web_search_calls: list[dict[str, Any]]


class StoryResult(StrictModel):
    story: Story
    status: Literal["excluded", "assessed", "written", "error"] = "excluded"
    relevance: Relevance | None = None
    assessment: Assessment | None = None
    calculation: CalculatedScore | None = None
    report: Report | None = None
    runs: dict[str, list[AgentRun]] = Field(default_factory=dict)
    error: str | None = None


class EvaluationResult(StrictModel):
    schema_version: str = "2.0"
    methodology_version: str = "1.0"
    calibration_effective_date: date = date(2026, 10, 7)
    methodology_profile: Literal["published", "custom"]
    generated_at: datetime
    config: dict[str, Any]
    prompt_sha256: dict[str, str]
    cumulative_points: EvidencePoints
    remaining_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    evidence_pressure_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
    complete: bool
    stories: list[StoryResult]

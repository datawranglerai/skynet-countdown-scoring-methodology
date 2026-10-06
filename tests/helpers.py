"""Small test fixtures containing evidence ratings without calculated values."""

from skynet_countdown.models import Assessment


def make_assessment(
    trifecta: tuple[int, int, int] = (0, 0, 0),
    amplifiers: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0),
) -> Assessment:
    amplifier_names = (
        "governance_vacuum",
        "autonomy_without_oversight",
        "human_capability_erosion",
        "sentience_self_preservation",
        "physical_weaponisation",
    )
    return Assessment.model_validate(
        {
            "trifecta": {
                name: {"score": score, "rationale": f"Evidence for {name}."}
                for name, score in zip(("t1", "t2", "t3"), trifecta, strict=True)
            },
            "amplifiers": {
                name: {"score": score, "rationale": f"Evidence for {name}."}
                for name, score in zip(amplifier_names, amplifiers, strict=True)
            },
            "is_leading_indicator": False,
            "leading_indicator_note": "",
            "scoring_notes": "Test evidence.",
        }
    )

from app.core.classification import PartyDisagreementSignal, classify_vote_type


def test_vote_type_is_voice_when_no_recorded_ballots() -> None:
    assert (
        classify_vote_type(
            description="Motion agreed to",
            yea_total=0,
            nay_total=0,
            disagreement_signals=[],
        )
        == "voice"
    )


def test_vote_type_is_confidence_for_budget_votes() -> None:
    assert (
        classify_vote_type(
            description="Budget implementation act at second reading",
            yea_total=160,
            nay_total=140,
            disagreement_signals=[],
        )
        == "confidence"
    )


def test_vote_type_is_free_when_any_party_has_high_disagreement() -> None:
    assert (
        classify_vote_type(
            description="Private member's bill",
            yea_total=180,
            nay_total=120,
            disagreement_signals=[PartyDisagreementSignal(party_slug="lib", disagreement_pct=17.5)],
        )
        == "free"
    )


def test_vote_type_defaults_to_whipped() -> None:
    assert (
        classify_vote_type(
            description="Government motion",
            yea_total=170,
            nay_total=130,
            disagreement_signals=[PartyDisagreementSignal(party_slug="lib", disagreement_pct=5.0)],
        )
        == "whipped"
    )

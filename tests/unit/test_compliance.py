from app.services.compliance_service import (
    calculate_pipeline_score,
    rating_meets_minimum,
    score_to_rating,
)


def test_score_to_rating():
    assert score_to_rating(95) == "Platinum"
    assert score_to_rating(80) == "Gold"
    assert score_to_rating(65) == "Silver"
    assert score_to_rating(45) == "Bronze"
    assert score_to_rating(20) == "Non-Compliant"


def test_calculate_pipeline_score_platinum():
    score, rating = calculate_pipeline_score(100, 100, 100, 100)
    assert score == 100.0
    assert rating == "Platinum"


def test_calculate_pipeline_score_weighted():
    # mandatory only 100%, rest 0%
    score, rating = calculate_pipeline_score(100, 0, 0, 0)
    assert score == 60.0
    assert rating == "Silver"


def test_rating_meets_minimum():
    assert rating_meets_minimum("Platinum", "Gold") is True
    assert rating_meets_minimum("Gold", "Gold") is True
    assert rating_meets_minimum("Silver", "Gold") is False
    assert rating_meets_minimum("Non-Compliant", "Bronze") is False

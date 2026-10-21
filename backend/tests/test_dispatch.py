from app.dispatch import distance_km, priority_for


def test_backend_keeps_existing_priority_scores_and_category_factors():
    assert priority_for("Ambulance / Medical Emergency", 5, 5)[0] == "Critical"
    assert priority_for("Fire and Rescue", 3, 3)[0] == "High"
    assert priority_for("Police / Security", 3, 3)[0] == "Medium"
    assert priority_for("Other Emergency", 1, 1)[0] == "Low"
    assert "= 22/22" in priority_for("Ambulance / Medical Emergency", 5, 5)[1]


def test_great_circle_distance_is_zero_same_point_and_symmetric():
    assert distance_km(30.7, 76.7, 30.7, 76.7) == 0
    assert abs(distance_km(30.7, 76.7, 30.8, 76.8) - distance_km(30.8, 76.8, 30.7, 76.7)) < 1e-9

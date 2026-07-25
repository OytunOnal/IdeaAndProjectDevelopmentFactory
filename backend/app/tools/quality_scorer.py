def calculate_quality_score(breakdown: dict) -> dict:
    """Calculate total quality score from category breakdown."""
    strategy = breakdown.get("strategy", 0)  # max 20
    product = breakdown.get("product", 0)  # max 25
    design = breakdown.get("design", 0)  # max 25
    technical = breakdown.get("technical", 0)  # max 30

    total = strategy + product + design + technical

    if total >= 90:
        grade = "A"
    elif total >= 80:
        grade = "B"
    elif total >= 70:
        grade = "C"
    elif total >= 60:
        grade = "D"
    else:
        grade = "F"

    return {
        "total": total,
        "grade": grade,
        "breakdown": breakdown,
        "passed": total >= 80,
    }

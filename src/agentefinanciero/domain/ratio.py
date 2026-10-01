def calculate_ratio(numerator: float, denominator: float) -> dict[str, float | str]:
    if denominator == 0:
        return {"error": "division by zero"}
    return {"result": numerator / denominator}

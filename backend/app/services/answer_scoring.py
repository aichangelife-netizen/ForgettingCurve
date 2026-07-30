def normalize_answer(answer: str) -> str:
    return answer.strip().casefold()


def check_answer(user_answer: str, canonical_answer: str) -> bool:
    return normalize_answer(user_answer) == normalize_answer(canonical_answer)

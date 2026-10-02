import re


def validate_iranian_national_id(national_id: str) -> bool:
    """Validate Iranian national ID (10 digits + standard checksum)."""
    if not re.fullmatch(r"\d{10}", national_id):
        return False

    if len(set(national_id)) == 1:
        return False

    check_digit = int(national_id[9])
    weighted_sum = sum(int(national_id[i]) * (10 - i) for i in range(9)) % 11

    if weighted_sum < 2:
        return check_digit == weighted_sum
    return check_digit == 11 - weighted_sum

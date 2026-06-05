from app.auth.security import get_password_hash, verify_password


def test_long_password_hash_and_verify() -> None:
    password = "a" * 200
    hashed = get_password_hash(password)
    assert verify_password(password, hashed) is True


def test_hash_is_not_plain_text() -> None:
    password = "MyStrongPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password

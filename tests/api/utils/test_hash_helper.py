from talk2dom.api.utils import hash_helper


def test_hash_and_verify_password_round_trip():
    hashed = hash_helper.hash_password("Secret123!")
    assert hashed != "Secret123!"
    assert hash_helper.verify_password("Secret123!", hashed) is True
    assert hash_helper.verify_password("wrong", hashed) is False

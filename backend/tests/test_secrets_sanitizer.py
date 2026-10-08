from pathlib import Path
from app.services.secrets_sanitizer import secrets_sanitizer_service, SecretsSanitizerService


def test_aws_access_key_redaction():
    code = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\nprint(AWS_KEY)'
    res = secrets_sanitizer_service.sanitize_text(code)

    assert res.findings_count >= 1
    assert any(f.secret_type == "aws_access_key" for f in res.findings)
    assert "AKIAIOSFODNN7EXAMPLE" not in res.sanitized_text
    assert "[REDACTED_SECRET:" in res.sanitized_text


def test_github_pat_redaction():
    code = 'const token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz";'
    res = secrets_sanitizer_service.sanitize_text(code)

    assert res.findings_count >= 1
    assert any(f.secret_type == "github_token" for f in res.findings)
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in res.sanitized_text
    assert "[REDACTED_SECRET:GITHUB_TOKEN]" in res.sanitized_text


def test_openai_api_key_redaction():
    code = 'openai.api_key = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfGhIjKlMnOpQrStUvWxYz"'
    res = secrets_sanitizer_service.sanitize_text(code)

    assert res.findings_count >= 1
    assert "sk-proj-" not in res.sanitized_text
    assert "[REDACTED_SECRET:" in res.sanitized_text


def test_private_key_redaction():
    key_block = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Y+n/9tW5yGqf...
-----END RSA PRIVATE KEY-----"""
    res = secrets_sanitizer_service.sanitize_text(key_block)

    assert res.findings_count >= 1
    assert any(f.secret_type == "private_key" for f in res.findings)
    assert "[REDACTED_SECRET:PRIVATE_KEY_BLOCK]" in res.sanitized_text


def test_shannon_entropy_calculation():
    # Low entropy (repetitive)
    low_entropy = SecretsSanitizerService.calculate_shannon_entropy("aaaaaaaaaaaaaaaa")
    assert low_entropy == 0.0

    # High entropy (random hex/base64 string)
    high_entropy = SecretsSanitizerService.calculate_shannon_entropy("9f8a3c4b1e2d7f6a5b4c3d2e1f0a9b8c")
    assert high_entropy > 3.5


def test_normal_code_not_falsely_redacted():
    clean_code = """
def calculate_area(radius: float) -> float:
    import math
    return math.pi * radius * radius

class OrderProcessor:
    def __init__(self, currency: str = "USD"):
        self.currency = currency
"""
    res = secrets_sanitizer_service.sanitize_text(clean_code)
    assert res.findings_count == 0
    assert res.sanitized_text == clean_code

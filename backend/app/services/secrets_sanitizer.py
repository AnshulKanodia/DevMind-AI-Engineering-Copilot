import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel


class SecretFinding(BaseModel):
    secret_type: str
    line_number: int
    start_pos: int
    end_pos: int
    masked_preview: str


class SanitizedContentResult(BaseModel):
    sanitized_text: str
    findings_count: int
    findings: List[SecretFinding]


class SecretsSanitizerService:
    """Pre-ingestion scanner that identifies and redacts secrets and credentials."""

    # Pre-compiled high-confidence regular expressions for known secret formats
    KNOWN_SECRET_PATTERNS: Dict[str, re.Pattern] = {
        "aws_access_key": re.compile(
            r"\b(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b"
        ),
        "github_token": re.compile(
            r"\b(ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|ghu_[a-zA-Z0-9]{36}|ghs_[a-zA-Z0-9]{36}|ghr_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{60,100})\b"
        ),
        "openai_api_key": re.compile(
            r"\b(sk-[a-zA-Z0-9]{40,60}|sk-proj-[a-zA-Z0-9_\-]{48,128})\b"
        ),
        "slack_token": re.compile(
            r"\bxox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9\-]*\b"
        ),
        "private_key": re.compile(
            r"-----BEGIN[ A-Z0-9_\-]*PRIVATE KEY-----[\s\S]*?-----END[ A-Z0-9_\-]*PRIVATE KEY-----"
        ),
        "generic_api_assignment": re.compile(
            r"""(?i)(?:password|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*["']([^"'\s]{8,})["']"""
        ),
        "jwt_token": re.compile(
            r"\beyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\b"
        ),
    }

    @staticmethod
    def calculate_shannon_entropy(data: str) -> float:
        """Calculate the Shannon entropy of a string to identify random keys/tokens."""
        if not data:
            return 0.0
        entropy = 0.0
        length = len(data)
        freq: Dict[str, int] = {}
        for char in data:
            freq[char] = freq.get(char, 0) + 1
        for count in freq.values():
            p_x = count / length
            entropy += -p_x * math.log2(p_x)
        return entropy

    @staticmethod
    def _mask_preview(secret_str: str) -> str:
        """Generate a safe masked preview of a detected secret for audit logs."""
        if len(secret_str) <= 8:
            return "****"
        return secret_str[:3] + "..." + secret_str[-3:]

    def sanitize_text(self, text: str) -> SanitizedContentResult:
        """Scan text line-by-line, detect secrets via regex and entropy, and redact them."""
        findings: List[SecretFinding] = []
        lines = text.splitlines(keepends=True)
        sanitized_lines: List[str] = []

        for line_idx, line in enumerate(lines, start=1):
            modified_line = line

            # 1. Check known specific pattern regexes
            for secret_type, pattern in self.KNOWN_SECRET_PATTERNS.items():
                if secret_type == "private_key":
                    continue  # Handled across full text below
                for match in pattern.finditer(modified_line):
                    matched_str = match.group(0)
                    # If regex has capture group (e.g. assignment), target the captured secret value
                    target_str = match.group(1) if match.lastindex and match.lastindex >= 1 else matched_str
                    
                    findings.append(
                        SecretFinding(
                            secret_type=secret_type,
                            line_number=line_idx,
                            start_pos=match.start(),
                            end_pos=match.end(),
                            masked_preview=self._mask_preview(target_str),
                        )
                    )
                    replacement = f"[REDACTED_SECRET:{secret_type.upper()}]"
                    modified_line = modified_line.replace(target_str, replacement)

            # 2. Check high-entropy tokens (e.g. hex or base64 credentials > 24 chars)
            # Find candidate continuous token words
            token_candidates = re.findall(r"\b[a-zA-Z0-9+/=_\-]{24,120}\b", modified_line)
            for candidate in token_candidates:
                # Exclude if already redacted or obvious non-secrets
                if "REDACTED_SECRET" in candidate or candidate.startswith("http"):
                    continue
                entropy = self.calculate_shannon_entropy(candidate)
                # Strings with high entropy (> 4.5) and significant length are almost certainly credentials
                if entropy > 4.5:
                    findings.append(
                        SecretFinding(
                            secret_type="high_entropy_token",
                            line_number=line_idx,
                            start_pos=modified_line.find(candidate),
                            end_pos=modified_line.find(candidate) + len(candidate),
                            masked_preview=self._mask_preview(candidate),
                        )
                    )
                    replacement = "[REDACTED_SECRET:HIGH_ENTROPY_TOKEN]"
                    modified_line = modified_line.replace(candidate, replacement)

            sanitized_lines.append(modified_line)

        sanitized_full_text = "".join(sanitized_lines)

        # 3. Full-text check for multi-line private keys
        pk_pattern = self.KNOWN_SECRET_PATTERNS["private_key"]
        for match in pk_pattern.finditer(sanitized_full_text):
            findings.append(
                SecretFinding(
                    secret_type="private_key",
                    line_number=1,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    masked_preview="-----BEGIN...KEY-----",
                )
            )
            sanitized_full_text = pk_pattern.sub(
                "[REDACTED_SECRET:PRIVATE_KEY_BLOCK]", sanitized_full_text
            )

        return SanitizedContentResult(
            sanitized_text=sanitized_full_text,
            findings_count=len(findings),
            findings=findings,
        )

    def sanitize_file(self, file_path: Path, in_place: bool = False) -> SanitizedContentResult:
        """Scan and sanitize a file on disk."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return SanitizedContentResult(sanitized_text="", findings_count=0, findings=[])

        result = self.sanitize_text(content)

        if in_place and result.findings_count > 0:
            file_path.write_text(result.sanitized_text, encoding="utf-8")

        return result


secrets_sanitizer_service = SecretsSanitizerService()

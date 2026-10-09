from app.services.semantic_chunker import semantic_chunker_service


PYTHON_CODE = '''class PaymentGateway:
    """Handles credit card transactions."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def process(self, amount: float) -> bool:
        """Process charge."""
        return amount > 0

def refund(transaction_id: str) -> bool:
    return True
'''


def test_chunk_file_preserves_semantics_and_lines():
    repo_id = "test-repo-123"
    file_path = "services/payment.py"

    chunks = semantic_chunker_service.chunk_file(repo_id, file_path, PYTHON_CODE)

    assert len(chunks) >= 3
    # Check that header comment is injected
    assert all("# File: services/payment.py" in c.content for c in chunks)

    # Check symbols
    symbol_names = [c.symbol_name for c in chunks]
    assert "PaymentGateway" in symbol_names
    assert "PaymentGateway.process" in symbol_names
    assert "refund" in symbol_names

    # Check deterministic chunk id
    refund_chunk = next(c for c in chunks if c.symbol_name == "refund")
    assert refund_chunk.start_line > 0
    assert refund_chunk.end_line >= refund_chunk.start_line
    assert len(refund_chunk.chunk_id) == 16
    assert refund_chunk.metadata["language"] == "python"


def test_chunk_repository_aggregation():
    repo_id = "test-repo-multi"
    files = {
        "src/payment.py": PYTHON_CODE,
        "src/util.ts": "export const greet = (name: string) => `Hello ${name}`;\n",
    }

    summary = semantic_chunker_service.chunk_repository(repo_id, files)

    assert summary.total_files_chunked == 2
    assert summary.total_chunks >= 4
    assert summary.total_tokens > 0
    assert summary.average_chunk_size_tokens > 0
    assert len(summary.chunks) == summary.total_chunks

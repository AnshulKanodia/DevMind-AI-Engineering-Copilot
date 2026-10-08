import os
from pathlib import Path
from typing import List, Set, Tuple, Optional
from pydantic import BaseModel


class SourceFileInfo(BaseModel):
    relative_path: str
    absolute_path: str
    extension: str
    size_bytes: int
    line_count: int


class FileFilterSummary(BaseModel):
    total_scanned: int
    eligible_count: int
    skipped_count: int
    total_code_lines: int
    eligible_files: List[SourceFileInfo]


class FileFilterService:
    """Intelligent repository file filter to isolate clean source code from noise and binaries."""

    # Maximum file size for AST parsing and embedding (1 MB)
    MAX_FILE_SIZE_BYTES = 1024 * 1024

    # Whitelist of primary code and config file extensions
    SUPPORTED_EXTENSIONS: Set[str] = {
        ".py", ".pyw",
        ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".java", ".kt", ".kts",
        ".go",
        ".rs",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".sql",
        ".sh", ".bash", ".zsh",
        ".html", ".css", ".scss", ".sass", ".less",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".markdown",
        ".proto", ".graphql", ".gql",
    }

    # Named files without standard code extensions that should be included
    SPECIAL_FILENAMES: Set[str] = {
        "dockerfile", "containerfile", "makefile", "gemfile", "procfile",
    }

    # Noisy directories to unconditionally skip
    IGNORED_DIRS: Set[str] = {
        ".git", ".github", ".gitlab", ".svn", ".hg",
        "node_modules", "bower_components",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".venv", "venv", "env", "virtualenv",
        "dist", "build", "target", "out", ".next", ".turbo", ".nuxt",
        "coverage", "htmlcov", ".tox",
        ".idea", ".vscode", ".vs",
        "vendor", "pods", "packages",
        "bin", "obj", "bundle",
        "logs", "tmp", "temp",
    }

    # Specific noisy or auto-generated files to skip
    IGNORED_FILENAMES: Set[str] = {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.lock",
        "poetry.lock",
        "cargo.lock",
        "gemfile.lock",
        "pipfile.lock",
        ".ds_store",
        "thumbs.db",
    }

    @classmethod
    def is_binary_file(cls, file_path: Path) -> bool:
        """Inspect file header using a null-byte test to detect binary content."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk
        except Exception:
            return True

    @classmethod
    def should_index_file(cls, file_path: Path, root_dir: Path) -> Tuple[bool, Optional[str]]:
        """Determine whether a file should be indexed, returning eligibility and rejection reason."""
        file_name = file_path.name.lower()
        ext = file_path.suffix.lower()

        # 1. Check exact ignored filename
        if file_name in cls.IGNORED_FILENAMES:
            return False, "ignored_filename"

        # 2. Check minified or map files
        if file_name.endswith(".min.js") or file_name.endswith(".min.css") or file_name.endswith(".map"):
            return False, "minified_or_sourcemap"

        # 3. Check extension / special filename whitelist
        if ext not in cls.SUPPORTED_EXTENSIONS and file_name not in cls.SPECIAL_FILENAMES:
            return False, "unsupported_extension"

        # 4. Check file size
        try:
            size = file_path.stat().st_size
        except OSError:
            return False, "unreadable"

        if size == 0:
            return False, "empty_file"

        if size > cls.MAX_FILE_SIZE_BYTES:
            return False, "file_too_large"

        # 5. Check binary content
        if cls.is_binary_file(file_path):
            return False, "binary_file"

        return True, None

    @classmethod
    def count_lines(cls, file_path: Path) -> int:
        """Count line numbers safely using utf-8 with replacement."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def scan_repository(self, repo_dir: Path) -> FileFilterSummary:
        """Walk repository tree, apply exclusion guards, and return clean code inventory."""
        repo_dir = repo_dir.resolve()
        total_scanned = 0
        eligible_files: List[SourceFileInfo] = []
        total_lines = 0

        for root, dirs, files in os.walk(repo_dir):
            # Prune noisy directories in-place so os.walk does not descend into them
            dirs[:] = [d for d in dirs if d.lower() not in self.IGNORED_DIRS and not d.startswith(".")]

            current_dir = Path(root)
            for f in files:
                total_scanned += 1
                file_path = current_dir / f

                is_eligible, _ = self.should_index_file(file_path, repo_dir)
                if is_eligible:
                    rel_path = str(file_path.relative_to(repo_dir)).replace("\\", "/")
                    size = file_path.stat().st_size
                    lines = self.count_lines(file_path)
                    total_lines += lines

                    eligible_files.append(
                        SourceFileInfo(
                            relative_path=rel_path,
                            absolute_path=str(file_path),
                            extension=file_path.suffix.lower(),
                            size_bytes=size,
                            line_count=lines,
                        )
                    )

        skipped_count = total_scanned - len(eligible_files)
        return FileFilterSummary(
            total_scanned=total_scanned,
            eligible_count=len(eligible_files),
            skipped_count=skipped_count,
            total_code_lines=total_lines,
            eligible_files=eligible_files,
        )


file_filter_service = FileFilterService()

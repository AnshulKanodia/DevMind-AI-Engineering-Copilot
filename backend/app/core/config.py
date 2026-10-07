import json
from functools import lru_cache
from typing import List, Literal, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DevMind Application Configuration with strict validation."""

    # Project metadata
    PROJECT_NAME: str = Field(default="DevMind", description="Name of the application")
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development", description="Deployment environment"
    )
    DEBUG: bool = Field(default=True, description="Debug mode flag")
    LOG_LEVEL: str = Field(default="INFO", description="Logging verbosity level")

    # Security & JWT Tokens
    SECRET_KEY: str = Field(
        default="devmind-super-secret-key-change-in-production-min-32-chars",
        description="Key used for cryptographic signing and session tokens",
    )
    # Fernet requires a 32-byte url-safe base64-encoded key
    ENCRYPTION_KEY: str = Field(
        default="r4Z3M6qI7yE7xW7E3vT2fR4dG9jL8nP1kQ5vY3bW6eI=",
        description="Base64 encoded 32-byte key for encrypting OAuth tokens at rest",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440, description="Expiration time for access tokens in minutes"
    )

    # CORS Configuration
    BACKEND_CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origin domains",
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            try:
                return json.loads(v)
            except Exception:
                return [v]
        return v

    # MongoDB Atlas Database & Vector Search
    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017/devmind?directConnection=true",
        description="MongoDB connection URI with Atlas Vector Search or local instance",
    )
    MONGODB_DB_NAME: str = Field(
        default="devmind", description="Target MongoDB database name"
    )
    MONGODB_VECTOR_INDEX_NAME: str = Field(
        default="vector_index", description="Atlas Vector Search index name"
    )

    # Redis Cache & Sessions
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and state management",
    )

    # OpenAI LLM & Embedding Models
    OPENAI_API_KEY: str = Field(
        default="sk-placeholder-key-for-dev",
        description="OpenAI API Key for GPT-4o and embedding models",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o", description="Default model for agent reasoning and code Q&A"
    )
    OPENAI_MINI_MODEL: str = Field(
        default="gpt-4o-mini", description="Lightweight model for summarization & fast routing"
    )
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small", description="Model for generating code vectors"
    )
    OPENAI_EMBEDDING_DIMENSIONS: int = Field(
        default=1536, description="Embedding vector dimensions"
    )

    # GitHub OAuth Integration
    GITHUB_CLIENT_ID: str = Field(
        default="devmind_github_client_id", description="GitHub OAuth App Client ID"
    )
    GITHUB_CLIENT_SECRET: str = Field(
        default="devmind_github_client_secret", description="GitHub OAuth App Client Secret"
    )
    GITHUB_REDIRECT_URI: str = Field(
        default="http://localhost:3000/auth/callback",
        description="OAuth callback URL",
    )

    # Observability & LangSmith
    LANGCHAIN_TRACING_V2: bool = Field(
        default=False, description="Enable LangSmith tracing"
    )
    LANGCHAIN_ENDPOINT: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint",
    )
    LANGCHAIN_API_KEY: str = Field(
        default="", description="LangSmith API Key"
    )
    LANGCHAIN_PROJECT: str = Field(
        default="devmind-copilot", description="LangSmith tracing project name"
    )

    # Sandbox & Ephemeral Ingestion
    SANDBOX_TEMP_DIR: str = Field(
        default="/tmp/devmind-sandboxes",
        description="Directory for isolated repository checkouts",
    )
    MAX_REPO_SIZE_MB: int = Field(
        default=500, description="Maximum allowed repository size in MB"
    )
    CLONE_TIMEOUT_SECONDS: int = Field(
        default=120, description="Maximum allowed time for git clone operations"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

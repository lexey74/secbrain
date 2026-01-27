from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class BotConfig(BaseSettings):
    """Configuration for SecBrain Bot"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    allowed_users_str: str = Field("", alias="TELEGRAM_ALLOWED_USERS")
    @property
    def allowed_users(self) -> List[int]:
        if not self.allowed_users_str:
            return []
        return [int(u) for u in self.allowed_users_str.split(",") if u.strip()]

    # Paths
    users_dir: Path = Field(Path("users"), alias="USERS_DIR")
    downloads_dir: Path = Field(Path("downloads"), alias="DOWNLOADS_DIR")

    # Models
    whisper_model: str = Field("small", alias="WHISPER_MODEL")
    whisper_threads: int = Field(16, alias="WHISPER_THREADS")

    # MCP
    mcp_host: str = Field("0.0.0.0", alias="MCP_HOST")
    mcp_port: int = Field(8000, alias="MCP_PORT")
    public_mcp_url: str = Field("http://localhost:8000", alias="PUBLIC_MCP_URL")
    mcp_jwt_secret: Optional[str] = Field(None, alias="MCP_JWT_SECRET")

    # Logs
    transcribe_log: Path = Path("logs/transcribe.log")
    ai_log: Path = Path("logs/ai.log")
    transcribe_pid: Path = Path("logs/transcribe.pid")
    ai_pid: Path = Path("logs/ai.pid")
    auth_file: Path = Path("auth.json")

    def model_post_init(self, __context):
        # Ensure directories exist
        self.transcribe_log.parent.mkdir(parents=True, exist_ok=True)

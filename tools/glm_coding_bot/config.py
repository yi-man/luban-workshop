"""GLM Coding Bot 配置管理"""

from dataclasses import dataclass, field
from pathlib import Path


def _default_user_data_dir() -> Path:
    return Path.home() / ".glm-coding-bot"


@dataclass
class Config:
    base_url: str = "https://bigmodel.cn"
    api_timeout: float = 2.0
    user_data_dir: Path = field(default_factory=_default_user_data_dir)
    target_product: str = "product-5d3a03"
    headless: bool = False
    poll_interval: float = 0.02
    max_poll_duration: float = 120.0


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config

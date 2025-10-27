import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str
    SECRET_KEY: str
    
    # Model Configuration
    GENERATOR_MODEL: str = "gpt-5-mini-2025-08-07"
    VALIDATOR_MODEL: str = "gpt-5-nano-2025-08-07"
    GENERATOR_TEMPERATURE: float = 0.7
    VALIDATOR_TEMPERATURE: float = 0.3
    
    # System Configuration
    MAX_CONCURRENT_ARTICLES: int = 3
    MAX_RETRIES: int = 5
    MAX_API_RETRIES: int = 4
    MIN_SCORE_THRESHOLD: float = 7.5
    PUBLISH_THRESHOLD: float = 8.5
    
    # Article Configuration
    MAX_WORD_COUNT: int = 1800
    MIN_WORD_COUNT: int = 800
    TARGET_LANGUAGE: str = "English"
    
    # Database
    DATABASE_PATH: str = "./medium_articles.db"
    
    # Logging
    LOG_FILE: str = "./article_generation.log"
    LOG_LEVEL: str = "INFO"
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    IMAGES_DIR: Path = STATIC_DIR / "images"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create necessary directories
        self.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()

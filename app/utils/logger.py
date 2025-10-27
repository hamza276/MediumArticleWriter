import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from app.config import settings

class CustomLogger:
    _instance: Optional['CustomLogger'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger('MediumArticleGenerator')
            self.logger.setLevel(getattr(logging, settings.LOG_LEVEL))
            
            # File handler
            log_path = Path(settings.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def info(self, message: str, **kwargs):
        self.logger.info(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        self.logger.critical(message, extra=kwargs)
    
    def log_node_execution(self, article_id: str, node_name: str, status: str, score: Optional[float] = None):
        message = f"Article {article_id} - Node: {node_name} - Status: {status}"
        if score is not None:
            message += f" - Score: {score:.2f}"
        self.info(message)
    
    def log_api_call(self, model: str, purpose: str, tokens: Optional[int] = None):
        message = f"API Call - Model: {model} - Purpose: {purpose}"
        if tokens:
            message += f" - Tokens: {tokens}"
        self.debug(message)
    
    def log_checkpoint(self, article_id: str, checkpoint_id: str, node_name: str):
        self.info(f"Checkpoint saved - Article: {article_id} - ID: {checkpoint_id} - Node: {node_name}")

logger = CustomLogger()


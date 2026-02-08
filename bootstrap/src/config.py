"""Configuration management"""

import yaml
from pathlib import Path
from typing import Any


class Config:
    """Configuration singleton"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: str = "config.yaml"):
        """Load configuration from YAML file"""
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                self._config = yaml.safe_load(f)
        else:
            # Default configuration
            self._config = {
                'database': {'path': 'data/wikigr.db'},
                'wikipedia': {
                    'user_agent': 'WikiGR/1.0 (Educational Project)',
                    'rate_limit_delay': 0.1,
                    'max_retries': 3,
                    'timeout': 30
                },
                'embeddings': {
                    'model_name': 'paraphrase-MiniLM-L3-v2',
                    'batch_size': 32,
                    'use_gpu': None
                },
                'expansion': {
                    'max_depth': 2,
                    'batch_size': 10,
                    'claim_timeout': 300,
                    'max_retries': 3
                },
                'logging': {
                    'level': 'INFO',
                    'file': 'logs/wikigr.log',
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                }
            }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        if self._config is None:
            self.load()

        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value


# Global config instance
config = Config()

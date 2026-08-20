"""
Configuration and settings for the ETL package.
"""

class Settings:
    """Holds ETL configuration values (env vars, connection strings, etc.)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


settings = Settings()

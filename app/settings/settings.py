import os

API_V1_STR: str = "/api/v1"
REDIS_URL: str = os.getenv("REDIS_URL")
DATABASE_URL: str = os.getenv("DATABASE_URL")
PROVIDER_A_API_KEY: str = os.getenv("PROVIDER_A_API_KEY")
PROVIDER_B_API_KEY: str = os.getenv("PROVIDER_B_API_KEY")
LOG_LEVEL: str = os.getenv("LOG_LEVEL")
ENV: str = os.getenv("ENV")

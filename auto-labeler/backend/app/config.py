"""Application configuration."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI")
    mongo_database: str = Field(default="auto_label_labeler", alias="MONGO_DATABASE")
    gcs_url_signed: bool = Field(default=False, alias="GCS_SIGN_URLS")
    gcs_url_ttl_seconds: int = Field(default=3600, alias="GCS_URL_TTL_SECONDS")
    google_credentials_file: Optional[str] = Field(default=None, alias="GOOGLE_APPLICATION_CREDENTIALS")
    namespace: str = Field(default="dataset-curation", alias="NAMESPACE")
    domain: str = Field(default="teknoir.cloud", alias="DOMAIN")

    model_config = ConfigDict(populate_by_name=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    values = {}
    for field_name, field_info in Settings.model_fields.items():
        env_key = field_info.alias or field_name
        env_val = os.getenv(env_key)
        if env_val is not None:
            values[field_name] = env_val
    return Settings(**values)

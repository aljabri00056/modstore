from datetime import datetime
from typing import Optional
import yaml
from pydantic import BaseModel, HttpUrl, Field, field_validator


class DyLib(BaseModel):
    name: str
    url: HttpUrl


class Version(BaseModel):
    version: str
    date: datetime
    description: str
    size: int = Field(..., description="Size in bytes")
    minOSVersion: Optional[str] = None
    decrypted_url: Optional[HttpUrl] = None
    tweaked_url: Optional[HttpUrl] = None


class App(BaseModel):
    name: str
    bundle_id: str
    store_url: HttpUrl
    dylibs: list[DyLib] = Field(default_factory=list)
    versions: list[Version] = Field(default_factory=list)

    @field_validator('dylibs', 'versions', mode='before')
    @classmethod
    def handle_none_lists(cls, v):
        """Convert None values to empty lists for dylibs and versions."""
        return v if v is not None else []


class AppsConfig(BaseModel):
    apps: list[App]

    @classmethod
    def from_yaml_file(cls, file_path: str) -> "AppsConfig":
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)
        return cls(**data)

    def to_yaml_file(self, file_path: str):
        """Save the configuration to a YAML file."""
        with open(file_path, 'w') as file:
            yaml.safe_dump(self.model_dump(mode='json'),
                           file, default_flow_style=False, sort_keys=False)


class DecryptionResult(BaseModel):
    file_path: str
    version: str

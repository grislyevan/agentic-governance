"""Endpoint profile Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _validate_behavioral_config(v: dict | None) -> dict | None:
    """Validate behavioral_config values: numbers must be positive, custom_llm_hosts must be list of strings."""
    if v is None:
        return v

    _NUMERIC_KEYS = {
        "shell_fanout_min_children",
        "shell_fanout_window_seconds",
        "llm_cadence_min_calls",
        "llm_cadence_min_connections",
        "llm_cadence_window_seconds",
        "burst_write_window_seconds",
        "burst_write_min_files",
        "burst_write_min_directories",
        "rmw_loop_window_seconds",
        "rmw_loop_min_cycles",
        "session_min_duration_seconds",
        "session_activity_gap_max_seconds",
        "credential_access_min_files",
        "credential_network_max_seconds_after_access",
        "git_automation_min_sequences",
        "resurrection_window_seconds",
        "resurrection_min_restarts",
        "execution_chain_window_seconds",
        "detection_threshold",
    }

    for key, value in v.items():
        if key == "custom_llm_hosts":
            if not isinstance(value, list):
                raise ValueError("custom_llm_hosts must be a list of strings")
            for item in value:
                if not isinstance(item, str):
                    raise ValueError("Each entry in custom_llm_hosts must be a string")
        elif key in _NUMERIC_KEYS:
            if not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a number")
            if value <= 0:
                raise ValueError(f"{key} must be positive")
    return v


class EndpointProfileConfig(BaseModel):
    """Per-profile agent config (subset used in create/update)."""
    scan_interval_seconds: int = Field(default=300, ge=30, le=86400)
    enforcement_posture: str = Field(default="passive", max_length=16, pattern="^(passive|audit|active)$")
    auto_enforce_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    policy_set_id: str | None = Field(default=None, max_length=128)
    behavioral_config: dict | None = Field(default=None)

    @field_validator("behavioral_config")
    @classmethod
    def validate_behavioral_config(cls, v: dict | None) -> dict | None:
        return _validate_behavioral_config(v)


class EndpointProfileCreate(BaseModel):
    name: str = Field(max_length=255)
    slug: str | None = Field(default=None, max_length=64)
    scan_interval_seconds: int = Field(default=300, ge=30, le=86400)
    enforcement_posture: str = Field(default="passive", max_length=16, pattern="^(passive|audit|active)$")
    auto_enforce_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    policy_set_id: str | None = Field(default=None, max_length=128)
    behavioral_config: dict | None = Field(default=None)

    @field_validator("behavioral_config")
    @classmethod
    def validate_behavioral_config(cls, v: dict | None) -> dict | None:
        return _validate_behavioral_config(v)


class EndpointProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    slug: str | None = Field(default=None, max_length=64)
    scan_interval_seconds: int | None = Field(default=None, ge=30, le=86400)
    enforcement_posture: str | None = Field(default=None, max_length=16, pattern="^(passive|audit|active)$")
    auto_enforce_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    policy_set_id: str | None = Field(default=None, max_length=128)
    behavioral_config: dict | None = Field(default=None)

    @field_validator("behavioral_config")
    @classmethod
    def validate_behavioral_config(cls, v: dict | None) -> dict | None:
        return _validate_behavioral_config(v)


class EndpointProfileResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    slug: str
    created_at: datetime
    scan_interval_seconds: int
    enforcement_posture: str
    auto_enforce_threshold: float
    policy_set_id: str | None
    behavioral_config: dict | None = None

    model_config = {"from_attributes": True}


class EndpointProfileListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[EndpointProfileResponse]

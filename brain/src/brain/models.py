"""Shared data shapes. `ObservationIn` is the contract with the Swift capture app."""

from datetime import datetime

from pydantic import BaseModel, Field


class ObservationIn(BaseModel):
    captured_at: datetime
    app_name: str
    bundle_id: str
    window_title: str = ""
    url: str | None = None
    text: str = Field(min_length=1)

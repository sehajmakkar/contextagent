"""Shared data shapes. `ObservationIn` is the contract with the Swift capture app."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ObservationIn(BaseModel):
    captured_at: datetime
    app_name: str
    bundle_id: str
    window_title: str = ""
    url: str | None = None
    text: str = Field(min_length=1)
    # Set by the Swift app (event-driven capture); None for fixture files.
    trigger: Literal["settled", "leaving", "poll"] | None = None

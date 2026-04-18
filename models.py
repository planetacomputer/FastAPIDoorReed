from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class EventIn(BaseModel):
    device_id: Optional[str] = Field(None, description="Device identifier")
    # state format historically could be '|0|1' or simple '0' — keep as str
    state: str = Field(..., description="Door state string, e.g. '0' or '|0|1'")
    rssi: Optional[float] = Field(None, description="Received signal strength")
    snr: Optional[float] = Field(None, description="Signal-to-noise ratio")
    battery: Optional[float] = Field(None, description="Battery voltage")
    contador: Optional[int] = Field(None, description="Optional event counter")


class EventOut(BaseModel):
    id: int
    device_id: Optional[str]
    state: str
    contador: Optional[int]
    rssi: Optional[float]
    snr: Optional[float]
    battery: Optional[float]
    timestamp: datetime
    # display fields (optional) populated by compute_row_display_fields
    timestamp_str: Optional[str] = None
    rssi_status: Optional[str] = None
    rssi_class: Optional[str] = None
    snr_status: Optional[str] = None
    snr_class: Optional[str] = None
    out_of_window: Optional[bool] = False

    # Pydantic v2-style config: prefer ConfigDict (from_attributes replaces orm_mode)
    model_config = ConfigDict(from_attributes=True, extra="allow")


class PostDoorResponse(BaseModel):
    status: str
    event: Optional[EventOut] = None

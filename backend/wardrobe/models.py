"""The shapes of the data, with their rules. Used by both the web API and the MCP server."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["top", "bottom", "outerwear", "shoes", "accessory", "fullbody"]
Season = Literal["spring", "summer", "autumn", "winter"]
CATEGORIES: tuple[str, ...] = Category.__args__
SEASONS: tuple[str, ...] = Season.__args__


class ItemUpdate(BaseModel):
    """Fields you (or Claude) can change. Leave a field out to keep it as it is."""
    name: Optional[str] = Field(None, max_length=80)
    category: Optional[Category] = None
    colors: Optional[list[str]] = Field(None, max_length=6)
    pattern: Optional[str] = Field(None, max_length=40)       # plain, striped, checked, ...
    formality: Optional[int] = Field(None, ge=1, le=5)        # 1 = gym, 5 = suit
    seasons: Optional[list[Season]] = None
    tags: Optional[list[str]] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=500)
    last_worn: Optional[str] = None                           # YYYY-MM-DD


class Item(BaseModel):
    id: str
    name: str
    category: Optional[Category]
    colors: list[str]
    pattern: Optional[str]
    formality: Optional[int]
    seasons: list[str]
    tags: list[str]
    notes: str
    created_at: str
    last_worn: Optional[str]
    images: dict[str, str]

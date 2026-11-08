"""The shapes of the data, with their rules. Used by both the web API and the MCP server."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

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


class OutfitItemIn(BaseModel):
    """One garment placed on the flat-lay canvas. x/y are its centre, 0..1 of the board."""
    item_id: str
    slot: Category
    x: float = Field(0.5, ge=0, le=1)
    y: float = Field(0.5, ge=0, le=1)
    z: int = Field(0, ge=0, le=50)          # stacking order: higher = on top


class OutfitIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    occasion: str = Field("", max_length=80)
    notes: str = Field("", max_length=1000)
    items: list[OutfitItemIn] = Field(..., min_length=1, max_length=12)

    @field_validator("items")
    @classmethod
    def no_duplicates(cls, items):
        ids = [i.item_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("an item can only appear once per outfit")
        return items


class OutfitItem(OutfitItemIn):
    name: str
    images: dict[str, str]


class Outfit(BaseModel):
    id: str
    name: str
    occasion: str
    notes: str
    created_by: Literal["liam", "claude"]
    created_at: str
    items: list[OutfitItem]


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


class AskIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, pattern=r"^[0-9a-f][0-9a-f-]{7,63}$")  # never a --flag

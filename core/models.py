"""Kieu du lieu dung chung cho toan app."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class BookBrief:
    """Ket qua tim kiem rut gon."""
    title: str
    url: str
    source: str = ""
    author: str = ""
    cover: str = ""
    latest: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Chapter:
    index: int          # so thu tu 1..n trong truyen
    title: str
    url: str
    volume: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Book:
    title: str
    url: str
    source: str = ""
    author: str = ""
    cover: str = ""
    description: str = ""
    status: str = ""
    genres: list = field(default_factory=list)
    chapters: list = field(default_factory=list)   # list[Chapter]

    def to_dict(self):
        return asdict(self)

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final, cast

from fastapi import FastAPI

from examples.fastapi import demo1, demo2, demo3, demo4, demo5, demo6, demo7
from examples.fastapi.shared import reset_store

SNAPSHOT_DIR: Final[Path] = Path(__file__).resolve().parent / "openapi"


@dataclass(frozen=True)
class Demo:
    module: ModuleType
    port: int

    @property
    def name(self) -> str:
        return self.module.__name__.rsplit(".", 1)[-1]

    @property
    def app(self) -> FastAPI:
        return cast(FastAPI, self.module.app)

    @property
    def app_path(self) -> str:
        return f"{self.module.__name__}:app"

    @property
    def snapshot_path(self) -> Path:
        return SNAPSHOT_DIR / f"{self.name}_openapi.json"


DEMO_MAP: Final[dict[str, Demo]] = {
    "1": Demo(demo1, 8000),
    "2": Demo(demo2, 8001),
    "3": Demo(demo3, 8002),
    "4": Demo(demo4, 8003),
    "5": Demo(demo5, 8004),
    "6": Demo(demo6, 8005),
    "7": Demo(demo7, 8006),
}


def load_snapshot(spec: Demo) -> dict[str, Any]:
    path = spec.snapshot_path
    if not path.exists():
        raise FileNotFoundError(path)
    return cast(dict[str, Any], json.loads(path.read_text()))


def reset_demo_store() -> None:
    reset_store()

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from fastapi import FastAPI

from examples.fastapi import demo1, demo2, demo3, demo4, demo5, demo6, demo7

SNAPSHOT_DIR: Final = (
    Path(__file__).resolve().parent.parent / "contract" / "openapi" / "snapshots"
)


@dataclass(frozen=True)
class DemoOpenAPIContract:
    name: str
    app: FastAPI

    def load_snapshot(self) -> dict[str, Any]:
        path = SNAPSHOT_DIR / f"{self.name}_openapi.json"
        if not path.exists():
            raise FileNotFoundError(path)
        return cast(dict[str, Any], json.loads(path.read_text()))


DEMO_OPENAPI_CONTRACTS: Final[tuple[DemoOpenAPIContract, ...]] = (
    DemoOpenAPIContract(name="demo1", app=demo1.app),
    DemoOpenAPIContract(name="demo2", app=demo2.app),
    DemoOpenAPIContract(name="demo3", app=demo3.app),
    DemoOpenAPIContract(name="demo4", app=demo4.app),
    DemoOpenAPIContract(name="demo5", app=demo5.app),
    DemoOpenAPIContract(name="demo6", app=demo6.app),
    DemoOpenAPIContract(name="demo7", app=demo7.app),
)

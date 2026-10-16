"""Write the API's OpenAPI schema to a file (used to generate the web app's TypeScript types).

Usage: python scripts/export_openapi.py ../../apps/web/openapi.json

Schemas that only ever appear in responses get every property marked required: the API always
serialises every field (``null`` where empty), so the generated types shouldn't be optional.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ENVIRONMENT", "development")

from app.main import app

REF_PREFIX = "#/components/schemas/"


def _refs(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(REF_PREFIX):
            found.add(ref.removeprefix(REF_PREFIX))
        for value in node.values():
            found |= _refs(value)
    elif isinstance(node, list):
        for value in node:
            found |= _refs(value)
    return found


def _closure(names: set[str], schemas: dict[str, Any]) -> set[str]:
    seen: set[str] = set()
    stack = list(names)
    while stack:
        name = stack.pop()
        if name in seen or name not in schemas:
            continue
        seen.add(name)
        stack.extend(_refs(schemas[name]) - seen)
    return seen


def tighten_response_schemas(spec: dict[str, Any]) -> dict[str, Any]:
    schemas = spec.get("components", {}).get("schemas", {})
    inputs: set[str] = set()
    outputs: set[str] = set()
    for operations in spec.get("paths", {}).values():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            inputs |= _refs(operation.get("requestBody", {}))
            inputs |= _refs(operation.get("parameters", []))
            outputs |= _refs(operation.get("responses", {}))
    output_only = _closure(outputs, schemas) - _closure(inputs, schemas)
    for name in output_only:
        schema = schemas[name]
        if schema.get("type") == "object" and "properties" in schema:
            schema["required"] = sorted(schema["properties"])
    return spec


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    spec = tighten_response_schemas(app.openapi())
    target.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()

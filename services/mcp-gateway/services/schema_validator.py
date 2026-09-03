"""Schema validator — validates data against JSON Schema definitions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


class SchemaValidator:
    """Load and validate data against JSON Schema files.

    Falls back gracefully when a schema file is missing — validation is
    treated as optional (``True``) in that case.
    """

    def __init__(self) -> None:
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._load_schemas()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_schemas(self) -> None:
        if not _SCHEMAS_DIR.exists():
            logger.warning("Schemas directory not found: %s", _SCHEMAS_DIR)
            return

        for path in _SCHEMAS_DIR.glob("*.schema.json"):
            try:
                with open(path) as fh:
                    data = json.load(fh)
                key = path.stem.replace(".schema", "")
                self._schemas[key] = data
            except Exception:
                logger.exception("Failed to load schema %s", path.name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, data: Dict[str, Any], schema_name: str) -> bool:
        """Validate *data* against the schema called *schema_name*.

        Returns ``True`` if validation passes.  Raises :class:`ValueError`
        on failure.  If the schema does not exist, returns ``True``.
        """
        schema = self._schemas.get(schema_name)
        if schema is None:
            return True

        try:
            import jsonschema  # type: ignore[import-untyped]

            jsonschema.validate(data, schema)
        except ImportError:
            # jsonschema not installed — skip validation
            logger.debug("jsonschema not installed; skipping validation for %s", schema_name)
            return True
        except jsonschema.ValidationError as exc:  # type: ignore[name-defined]
            raise ValueError(f"Schema validation failed for {schema_name}: {exc.message}") from exc

        return True

    def get_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        return self._schemas.get(schema_name)

    def list_schemas(self) -> List[str]:
        return sorted(self._schemas.keys())

    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """Register a schema at runtime (useful for tests)."""
        self._schemas[name] = schema


# Module-level singleton
schema_validator = SchemaValidator()

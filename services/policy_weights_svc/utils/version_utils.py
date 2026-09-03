"""Version management utilities for semantic versioning of weight policies."""

import re
from typing import Optional


class VersionUtils:
    """Utilities for version management."""

    _PATTERN = re.compile(r"^v(\d+)\.(\d+)$")

    @staticmethod
    def parse(version: str) -> tuple[int, int]:
        """Parse a version string into (major, minor).

        Returns (0, 0) if the version string is malformed.
        """
        m = VersionUtils._PATTERN.match(version)
        if m:
            return int(m.group(1)), int(m.group(2))
        return (0, 0)

    @staticmethod
    def format(major: int, minor: int) -> str:
        return f"v{major}.{minor}"

    @staticmethod
    def increment(version: str, bump: str = "minor") -> str:
        """Increment a version string.

        ``bump="minor"``  →  v1.3 → v1.4
        ``bump="major"``  →  v1.3 → v2.0
        ``bump="patch"``  →  not used, alias for minor.
        """
        major, minor = VersionUtils.parse(version)
        if major == 0 and minor == 0:
            return "v1.0"

        if bump == "major":
            return VersionUtils.format(major + 1, 0)
        return VersionUtils.format(major, minor + 1)

    @staticmethod
    def compare(v1: str, v2: str) -> int:
        """Compare two version strings.

        Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2.
        """
        p1 = VersionUtils.parse(v1)
        p2 = VersionUtils.parse(v2)

        if p1[0] != p2[0]:
            return -1 if p1[0] < p2[0] else 1
        if p1[1] != p2[1]:
            return -1 if p1[1] < p2[1] else 1
        return 0

    @staticmethod
    def is_between(version: str, start: str, end: str) -> bool:
        """Check if version is in [start, end]."""
        return (
            VersionUtils.compare(version, start) >= 0
            and VersionUtils.compare(version, end) <= 0
        )

    @staticmethod
    def validate(version: str) -> bool:
        """Check if version string is well-formed."""
        return VersionUtils._PATTERN.match(version) is not None

    @staticmethod
    def latest(versions: list[str]) -> Optional[str]:
        """Return the highest version from a list, or None."""
        if not versions:
            return None
        return max(versions, key=lambda v: VersionUtils.parse(v))

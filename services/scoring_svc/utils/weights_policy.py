"""Weight policy manager for versioned detector weights."""

import json
from datetime import datetime, timezone
from pathlib import Path

from ..models.scoring import WeightConfig


class WeightPolicyManager:
    """Manages versioned weight policies for detector signals."""

    def __init__(self, policy_dir: str = "policies"):
        self.policy_dir = Path(policy_dir)
        self._cache: dict[str, WeightConfig] = {}
        self._load_policies()

    def _load_policies(self):
        """Load all weight policies from the policy directory."""
        if not self.policy_dir.exists():
            self._create_default_policies()

        for policy_file in self.policy_dir.glob("weights_*.json"):
            with open(policy_file) as f:
                data = json.load(f)
                config = WeightConfig(**data)
                self._cache[config.version] = config

    def _create_default_policies(self):
        """Create default weight policies if none exist."""
        self.policy_dir.mkdir(exist_ok=True)

        # Default weights from project specification
        default_weights = {
            "price_deviation": 0.30,
            "duplicate_fuzzy": 0.20,
            "vendor_graph_risk": 0.20,
            "timing_anomaly": 0.10,
            "contract_splitting": 0.15,
            "approval_velocity": 0.05,
        }

        config = WeightConfig(
            version="v1.0",
            weights=default_weights,
            effective_from=datetime(2024, 1, 1),
            description="Initial production weights from project spec",
        )
        self._save_policy(config)

    def _save_policy(self, config: WeightConfig):
        """Save policy to JSON file."""
        filepath = self.policy_dir / f"weights_{config.version}.json"
        with open(filepath, "w") as f:
            json.dump(config.model_dump(), f, default=str, indent=2)

    def get_weights(self, version: str | None = None) -> WeightConfig:
        """Get weights by version or latest."""
        if version:
            if version not in self._cache:
                raise ValueError(f"Weights version '{version}' not found")
            return self._cache[version]

        # Return latest version
        if not self._cache:
            raise ValueError("No weight policies found")
        latest = max(self._cache.keys(), key=lambda v: tuple(map(int, v.lstrip("v").split("."))))
        return self._cache[latest]

    def create_version(
        self,
        weights: dict[str, float],
        description: str = "",
    ) -> WeightConfig:
        """Create a new weight version."""
        # Validate weights sum to 1.0
        total = sum(weights.values())
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"Weights must sum to 1.0 (got {total:.4f})")

        # Generate next version - increment major version for new major releases
        versions = [v for v in self._cache if v.startswith("v")]
        if versions:
            latest = max(versions, key=lambda v: tuple(map(int, v.lstrip("v").split("."))))
            major, minor = map(int, latest.lstrip("v").split("."))
            new_version = f"v{major + 1}.0"
        else:
            new_version = "v1.0"

        config = WeightConfig(
            version=new_version,
            weights=weights,
            effective_from=datetime.now(timezone.utc),
            description=description or f"Weight version {new_version}",
        )

        self._cache[config.version] = config
        self._save_policy(config)
        return config

    def list_versions(self) -> list[str]:
        """List all available weight versions."""
        return sorted(self._cache.keys(), reverse=True)
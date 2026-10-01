import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from colorstack_ai.playbooks.models import PlaybookDefinition


class PlaybookError(RuntimeError):
    pass


def default_playbook_directory() -> Path:
    return Path(__file__).resolve().parents[3] / "playbooks"


def definition_hash(definition: PlaybookDefinition) -> str:
    serialized = json.dumps(
        definition.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


class PlaybookLoader:
    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or default_playbook_directory()

    def load_all(self) -> list[PlaybookDefinition]:
        paths = sorted(self._directory.glob("*.yaml"))
        paths.extend(sorted((self._directory / "overlays").glob("*.yaml")))
        paths.extend(sorted((self._directory / "custom").glob("**/*.yaml")))
        if not paths:
            raise PlaybookError(
                f"No playbook definitions found in {self._directory}"
            )

        raw_by_key: dict[str, dict[str, Any]] = {}
        source_by_key: dict[str, Path] = {}
        for path in paths:
            try:
                loaded = yaml.safe_load(path.read_text())
            except (OSError, yaml.YAMLError) as error:
                raise PlaybookError(f"Could not load {path}: {error}") from error
            if not isinstance(loaded, dict):
                raise PlaybookError(f"{path} must contain a YAML mapping")
            key = loaded.get("key")
            if not isinstance(key, str) or not key:
                raise PlaybookError(f"{path} is missing a playbook key")
            if key in raw_by_key:
                raise PlaybookError(
                    f"Duplicate playbook key {key!r} in {path} and "
                    f"{source_by_key[key]}"
                )
            raw_by_key[key] = loaded
            source_by_key[key] = path

        resolved: dict[str, PlaybookDefinition] = {}
        visiting: set[str] = set()

        def resolve(key: str) -> PlaybookDefinition:
            if key in resolved:
                return resolved[key]
            if key in visiting:
                raise PlaybookError(f"Circular playbook extension at {key!r}")
            raw = raw_by_key.get(key)
            if raw is None:
                raise PlaybookError(f"Unknown extended playbook {key!r}")

            visiting.add(key)
            merged_requirements: dict[str, dict[str, Any]] = {}
            extends = raw.get("extends", [])
            if not isinstance(extends, list):
                raise PlaybookError(f"{key}.extends must be a list")
            for parent_key in extends:
                if not isinstance(parent_key, str):
                    raise PlaybookError(f"{key}.extends values must be strings")
                parent = resolve(parent_key)
                for requirement in parent.requirements:
                    merged_requirements[requirement.key] = (
                        requirement.model_dump(mode="json")
                    )

            requirements = raw.get("requirements", [])
            if not isinstance(requirements, list):
                raise PlaybookError(f"{key}.requirements must be a list")
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    raise PlaybookError(
                        f"{key} requirements must be mappings"
                    )
                requirement_key = requirement.get("key")
                if not isinstance(requirement_key, str):
                    raise PlaybookError(
                        f"{key} contains a requirement without a key"
                    )
                base = merged_requirements.get(requirement_key, {})
                merged_requirements[requirement_key] = {
                    **base,
                    **requirement,
                }

            merged = {
                **raw,
                "requirements": list(merged_requirements.values()),
            }
            try:
                definition = PlaybookDefinition.model_validate(merged)
            except ValidationError as error:
                raise PlaybookError(
                    f"Invalid playbook {source_by_key[key]}: {error}"
                ) from error

            requirement_keys = {
                requirement.key for requirement in definition.requirements
            }
            for requirement in definition.requirements:
                missing = set(requirement.dependencies) - requirement_keys
                if missing:
                    raise PlaybookError(
                        f"{key}.{requirement.key} has unknown dependencies: "
                        f"{', '.join(sorted(missing))}"
                    )
            visiting.remove(key)
            resolved[key] = definition
            return definition

        return [resolve(key) for key in sorted(raw_by_key)]

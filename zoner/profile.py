"""Stable identity and component versions for the Zoner v0 runtime.

Zoner v0 is intentionally an orchestration runtime over replaceable foundation
models.  Keeping these versions together makes prompt, retrieval, tool-policy,
and evaluation changes observable and reversible without pretending that
Vigzone trained the active base model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ZonerProfile:
    """Immutable release identity attached to every Zoner-assisted response."""

    name: str
    release: str
    version: str
    status: str
    prompt_bundle_version: str
    retrieval_policy_version: str
    tool_policy_version: str
    evaluation_suite_version: str
    architecture: str
    base_model_owned_by_vigzone: bool
    capabilities: tuple[str, ...]

    def runtime_metadata(self) -> dict[str, Any]:
        """Return compact metadata suitable for response and usage traces."""

        return {
            "name": self.name,
            "release": self.release,
            "version": self.version,
            "prompt_bundle_version": self.prompt_bundle_version,
            "retrieval_policy_version": self.retrieval_policy_version,
            "tool_policy_version": self.tool_policy_version,
            "evaluation_suite_version": self.evaluation_suite_version,
        }

    def public_manifest(self) -> dict[str, Any]:
        """Return the truthful, non-secret public description of this release."""

        manifest = asdict(self)
        manifest["capabilities"] = list(self.capabilities)
        manifest["training_state"] = "no_custom_weights"
        manifest["private_data_training"] = False
        return manifest


ZONER_PROFILE = ZonerProfile(
    name="Zoner",
    release="v0",
    version="0.1.0",
    status="development_integration",
    prompt_bundle_version="zoner-prompt-v0.9",
    retrieval_policy_version="private-lexical-v1",
    tool_policy_version="bounded-context-tools-v1",
    evaluation_suite_version="zoner-evals-v0.9",
    architecture="versioned_orchestration_runtime",
    base_model_owned_by_vigzone=False,
    capabilities=(
        "versioned_prompting",
        "private_context_retrieval",
        "bounded_live_context",
        "task_routing",
        "offline_evaluations",
    ),
)


def zoner_manifest() -> dict[str, Any]:
    """Return the active Zoner release manifest."""

    return ZONER_PROFILE.public_manifest()

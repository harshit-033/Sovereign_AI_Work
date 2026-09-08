"""Capability-based routing for the local workbench."""

from .classifier import CapabilityClassifier
from .config import RoutingConfig, RoutingConfigurationError
from .handlers import CapabilityHandler
from .models import (
    CapabilityDefinition,
    CapabilityHealth,
    CapabilityId,
    RoutingContext,
    RoutingDecision,
)
from .registry import CapabilityRegistry, build_default_registry
from .router import (
    CapabilityNotAllowedError,
    CapabilityUnavailableError,
    RouterDisabledError,
    UnknownCapabilityError,
    CapabilityRouter,
)

__all__ = [
    "CapabilityClassifier",
    "CapabilityDefinition",
    "CapabilityHealth",
    "CapabilityHandler",
    "CapabilityId",
    "CapabilityNotAllowedError",
    "CapabilityRegistry",
    "CapabilityRouter",
    "CapabilityUnavailableError",
    "RoutingConfig",
    "RoutingConfigurationError",
    "RoutingContext",
    "RoutingDecision",
    "RouterDisabledError",
    "UnknownCapabilityError",
    "build_default_registry",
]

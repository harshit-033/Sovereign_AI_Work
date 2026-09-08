from __future__ import annotations

import time
from typing import Mapping, Optional

from .classifier import CapabilityClassifier
from .config import RoutingConfig
from .models import CapabilityHealth, CapabilityId, RoutingContext, RoutingDecision
from .registry import CapabilityRegistry


class RouterDisabledError(RuntimeError):
    pass


class UnknownCapabilityError(ValueError):
    pass


class CapabilityNotAllowedError(PermissionError):
    pass


class CapabilityUnavailableError(RuntimeError):
    pass


_MODE_CAPABILITIES = {
    "general": CapabilityId.GENERAL_CHAT,
    "general chat": CapabilityId.GENERAL_CHAT,
    "document": CapabilityId.DOCUMENT_ANALYSIS,
    "document analysis": CapabilityId.DOCUMENT_ANALYSIS,
    "knowledge": CapabilityId.KNOWLEDGE_RAG,
    "knowledge chat": CapabilityId.KNOWLEDGE_RAG,
    "rag": CapabilityId.KNOWLEDGE_RAG,
    "agent": CapabilityId.AGENT_TASK,
    "agent task": CapabilityId.AGENT_TASK,
}


class CapabilityRouter:
    def __init__(self, config: RoutingConfig, registry: CapabilityRegistry, classifier: Optional[CapabilityClassifier] = None):
        self.config = config
        self.registry = registry
        self.classifier = classifier or CapabilityClassifier()

    @staticmethod
    def _normalize_mode(mode: Optional[str]) -> str:
        return " ".join((mode or "auto").casefold().replace("_", " ").split())

    def _definition(self, capability: CapabilityId, context: RoutingContext):
        if not self.registry.contains(capability):
            raise UnknownCapabilityError(f"Unknown capability: {capability.value}")
        if capability not in context.available_capabilities:
            raise CapabilityNotAllowedError(f"Capability is not available for this request: {capability.value}")
        definition = self.registry.get(capability)
        if not definition.enabled:
            raise CapabilityUnavailableError(f"Capability {capability.value} is disabled.")
        if definition.requires_document and not context.selected_document_id:
            raise CapabilityUnavailableError("DOCUMENT_ANALYSIS requires a selected session document.")
        if definition.requires_knowledge_base and not context.knowledge_base_available:
            raise CapabilityUnavailableError("KNOWLEDGE_RAG is unavailable because the knowledge base is disabled.")
        return definition

    def _decision(self, capability, confidence, reason_code, reason, explicit, started, context):
        definition = self._definition(capability, context)
        return RoutingDecision(
            capability=capability,
            display_name=definition.display_name,
            confidence=round(confidence, 2),
            reason_code=reason_code,
            reason=reason,
            model_name=definition.model_name,
            handler=definition.handler,
            requires_document=definition.requires_document,
            requires_knowledge_base=definition.requires_knowledge_base,
            explicit=explicit,
            routing_latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )

    def route(self, context: RoutingContext) -> RoutingDecision:
        if not self.config.enabled:
            raise RouterDisabledError("Capability routing is disabled. Set SIH_ROUTING_ENABLED=1.")
        started = time.perf_counter()
        mode = self._normalize_mode(context.selected_mode)
        if mode != "auto":
            capability = _MODE_CAPABILITIES.get(mode)
            if not capability:
                raise UnknownCapabilityError(f"Unknown chat mode: {context.selected_mode}")
            return self._decision(
                capability, 1.0, "explicit_mode", f"The user explicitly selected {self.registry.get(capability).display_name}.", True, started, context
            )
        if not self.config.auto_enabled:
            raise CapabilityUnavailableError("Auto routing is disabled. Select an explicit chat mode.")
        capability, confidence, reason_code, reason = self.classifier.classify(context)
        return self._decision(capability, confidence, reason_code, reason, False, started, context)

    def health(
        self,
        model_health: Mapping[str, Mapping[str, object]],
        rag_enabled: bool,
        ocr_ready: bool,
    ) -> list[CapabilityHealth]:
        result: list[CapabilityHealth] = []
        for definition in self.registry.all():
            model = model_health.get(definition.model_name, {})
            available = bool(model.get("connected") and model.get("model_available"))
            reason = ""
            if not available:
                reason = f"Configured model '{definition.model_name}' is unavailable."
            elif definition.capability_id == CapabilityId.DOCUMENT_ANALYSIS and not ocr_ready:
                available = False
                reason = "Tesseract OCR is unavailable."
            elif definition.capability_id == CapabilityId.KNOWLEDGE_RAG and not rag_enabled:
                available = False
                reason = "Knowledge base is disabled."
            result.append(
                CapabilityHealth(
                    definition.capability_id,
                    available,
                    definition.model_name,
                    definition.handler,
                    reason,
                    definition.display_name,
                )
            )
        return result

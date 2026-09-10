"""
Cordis Microkernel Implementation for DeepSeek Harness (Python Edition).
Implements the core architectural principles of DeepSeek Harness:
1. No Privileged Core ("一切皆插件" - Everything is a Plugin)
2. Service Container & Dependency Injection (Context & Service Provider)
3. Event-Driven Lifecycle Hooks (Mount, Apply, Start, Stop)
4. Append-Only Traceable Session Log (Audit & Replay Engine)
"""

import time
from typing import Dict, Any, List, Callable, Optional, Type
from pydantic import BaseModel, Field


class TraceEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    event_type: str
    source_plugin: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class SessionLogger:
    """Append-only, immutable trace recorder for full auditability and replay."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._traces: List[TraceEntry] = []

    def record(self, event_type: str, source_plugin: str, payload: Dict[str, Any]):
        entry = TraceEntry(
            event_type=event_type,
            source_plugin=source_plugin,
            payload=payload
        )
        self._traces.append(entry)

    def get_traces(self) -> List[TraceEntry]:
        return list(self._traces)


class Context:
    """
    Cordis Context Container:
    The backbone of DeepSeek Harness. Manages services, plugins, and lifecycle hooks.
    """
    def __init__(self, parent: Optional["Context"] = None):
        self.parent = parent
        self._services: Dict[str, Any] = {}
        self._plugins: Dict[str, Any] = {}
        self._event_listeners: Dict[str, List[Callable]] = {}
        self.session_logger: Optional[SessionLogger] = None

    def provide(self, service_name: str, service_instance: Any):
        """Register a service into the context container."""
        self._services[service_name] = service_instance
        self.emit("service.registered", {"name": service_name, "instance": service_instance})

    def get(self, service_name: str) -> Optional[Any]:
        """Retrieve a service from container or parent context."""
        if service_name in self._services:
            return self._services[service_name]
        if self.parent:
            return self.parent.get(service_name)
        return None

    def on(self, event_name: str, handler: Callable):
        """Subscribe to a typed event."""
        if event_name not in self._event_listeners:
            self._event_listeners[event_name] = []
        self._event_listeners[event_name].append(handler)

    def emit(self, event_name: str, data: Any = None):
        """Broadcast an event to all subscribers."""
        if self.session_logger:
            self.session_logger.record(
                event_type=event_name,
                source_plugin="cordis_kernel",
                payload=data if isinstance(data, dict) else {"data": str(data)}
            )
        listeners = self._event_listeners.get(event_name, [])
        for handler in listeners:
            try:
                handler(data)
            except Exception as e:
                print(f"[Error in event handler for '{event_name}']: {e}")
        if self.parent:
            self.parent.emit(event_name, data)

    def plugin(self, plugin_cls_or_instance: Any, config: Optional[Dict[str, Any]] = None):
        """Mount a plugin into the Cordis Context."""
        config = config or {}
        if isinstance(plugin_cls_or_instance, type):
            instance = plugin_cls_or_instance()
        else:
            instance = plugin_cls_or_instance

        plugin_id = getattr(instance, "name", getattr(instance, "plugin_id", instance.__class__.__name__))
        self._plugins[plugin_id] = instance

        # Execute plugin apply hook
        if hasattr(instance, "apply"):
            instance.apply(self, config)

        self.emit("plugin.mounted", {"plugin_id": plugin_id, "config": config})
        return instance

    def create_session(self, session_id: str) -> "Context":
        """Fork a session context with an isolated SessionLogger."""
        child_ctx = Context(parent=self)
        child_ctx.session_logger = SessionLogger(session_id=session_id)
        return child_ctx

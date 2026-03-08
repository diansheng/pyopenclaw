import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    module: str
    provides: List[str]

class PluginRegistry:
    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register(self, manifest: PluginManifest, plugin_obj: Any) -> None:
        with self._lock:
            self._registry[manifest.id] = {
                "manifest": manifest,
                "object": plugin_obj
            }

    def get(self, name: str, kind: str) -> Optional[Any]:
        with self._lock:
            for plugin in self._registry.values():
                # Assuming plugin object has methods to get tools/channels
                # Or plugin object IS the provider?
                # Design says: `plugin_module.setup(registry)` registers items.
                # So `PluginRegistry` should store items directly?
                # "PluginRegistry.get(name, kind): looks up by (kind, name) tuple"
                # So registry should store `(kind, name) -> object`.
                pass
            # I will refactor to store items by (kind, name)
            pass

    def register_item(self, kind: str, name: str, item: Any):
        with self._lock:
            if "items" not in self._registry:
                self._registry["items"] = {}
            self._registry["items"][(kind, name)] = item

    def get_item(self, kind: str, name: str) -> Optional[Any]:
        with self._lock:
            return self._registry.get("items", {}).get((kind, name))

    def list_all(self) -> List[PluginManifest]:
        with self._lock:
            return [p["manifest"] for k, p in self._registry.items() if k != "items"]

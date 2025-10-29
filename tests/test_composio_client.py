"""Tests autour du client Composio."""
from __future__ import annotations

from importlib import util as importlib_util
from pathlib import Path
from typing import Dict, List
import sys
import types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = PROJECT_ROOT / "src" / "mcp_customer_service"

package = types.ModuleType("mcp_customer_service")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules.setdefault("mcp_customer_service", package)


class _SettingsStub:
    def __init__(self, composio_api_key: str = "", telegram_bot_token: str = "", **_: str) -> None:
        self.composio_api_key = composio_api_key
        self.telegram_bot_token = telegram_bot_token


def _get_settings_stub() -> _SettingsStub:
    return _SettingsStub()


config_stub = types.ModuleType("mcp_customer_service.config")
config_stub.Settings = _SettingsStub
config_stub.get_settings = _get_settings_stub
sys.modules["mcp_customer_service.config"] = config_stub


class _BaseModelStub:
    def __init__(self, **data):
        for key, value in data.items():
            setattr(self, key, value)

    def dict(self, **_: str):
        return dict(self.__dict__)


def _field_stub(*_args, default=None, default_factory=None, **_kwargs):
    if default_factory is not None:
        return default_factory()
    return default


pydantic_stub = types.ModuleType("pydantic")
pydantic_stub.BaseModel = _BaseModelStub
pydantic_stub.Field = _field_stub
sys.modules.setdefault("pydantic", pydantic_stub)


def _load_module(module_name: str, relative_path: str):
    module_path = PROJECT_ROOT / relative_path
    spec = importlib_util.spec_from_file_location(module_name, module_path)
    module = importlib_util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader  # nosec - vérification simple pour les tests
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


composio_module = _load_module(
    "mcp_customer_service.composio_client",
    "src/mcp_customer_service/composio_client.py",
)

ComposioClient = getattr(composio_module, "ComposioClient")
SupportChannel = getattr(_load_module(
    "mcp_customer_service.channels",
    "src/mcp_customer_service/channels.py",
), "SupportChannel")
Settings = _SettingsStub


class _DummyConnectors:
    def __init__(self, items: List[Dict[str, str]]) -> None:
        self._items = items

    def list(self):  # pragma: no cover - méthode simple
        return {"items": self._items}


class _DummyActions:
    def __init__(self, mapping: Dict[str, List[Dict[str, str]]]) -> None:
        self._mapping = mapping

    def list(self, connector: str | None = None):  # pragma: no cover - méthode simple
        if connector:
            return self._mapping.get(connector, [])
        merged: List[Dict[str, str]] = []
        for values in self._mapping.values():
            merged.extend(values)
        return merged


class _DummyInstallations:
    def __init__(self) -> None:
        self.created_payloads: List[Dict[str, str]] = []

    def create_installation_link(self, **payload):  # pragma: no cover - simple stub
        self.created_payloads.append(payload)
        return {"url": "https://composio.test/install", "connector": payload.get("connector")}

    def list(self, **_kwargs):  # pragma: no cover - simple stub
        return [
            {"connector": "gmail", "status": "installed"},
            {"connector": "whatsapp", "status": "pending"},
        ]


def test_list_available_tools_simulated_mode():
    settings = Settings(composio_api_key="")
    client = ComposioClient(settings)

    info = client.list_available_tools()

    assert info["mode"] == "simulated"
    connectors = {entry["channel"]: entry for entry in info["connectors"]}
    assert connectors["whatsapp"]["available"] is False
    assert "reason" in connectors["whatsapp"]


def test_list_available_tools_live_mode():
    settings = Settings(composio_api_key="dummy")
    client = ComposioClient(settings)

    dummy_client = type(
        "DummyClient",
        (),
        {
            "connectors": _DummyConnectors(
                [
                    {"slug": "whatsapp"},
                    {"slug": "linkedin"},
                ]
            ),
            "actions": _DummyActions(
                {
                    "whatsapp": [{"name": "send_message"}],
                    "linkedin": [{"name": "send_message"}],
                }
            ),
            "installations": _DummyInstallations(),
        },
    )()

    client._client = dummy_client  # type: ignore[attr-defined]

    info = client.list_available_tools()

    assert info["mode"] == "live"
    connectors = {entry["channel"]: entry for entry in info["connectors"]}
    assert connectors["whatsapp"]["available"] is True
    assert connectors["linkedin"]["available"] is True


def test_generate_installation_link_simulated_mode():
    settings = Settings(composio_api_key="")
    client = ComposioClient(settings)

    link = client.generate_installation_link(SupportChannel.gmail, external_user_id="42")

    assert link["status"] == "simulated"
    assert "url" in link


def test_generate_installation_link_live_mode():
    settings = Settings(composio_api_key="dummy")
    client = ComposioClient(settings)

    installations = _DummyInstallations()
    dummy_client = type(
        "DummyClient",
        (),
        {
            "connectors": _DummyConnectors([{"slug": "gmail"}]),
            "actions": _DummyActions({"gmail": [{"name": "send_email"}]}),
            "installations": installations,
        },
    )()

    client._client = dummy_client  # type: ignore[attr-defined]

    link = client.generate_installation_link(SupportChannel.gmail, external_user_id="100")

    assert link["status"] == "live"
    assert link.get("url") == "https://composio.test/install"
    assert installations.created_payloads[0]["connector"] == "gmail"


def test_list_user_installations_live_mode():
    settings = Settings(composio_api_key="dummy")
    client = ComposioClient(settings)

    dummy_client = type(
        "DummyClient",
        (),
        {
            "connectors": _DummyConnectors([{"slug": "gmail"}]),
            "actions": _DummyActions({"gmail": [{"name": "send_email"}]}),
            "installations": _DummyInstallations(),
        },
    )()

    client._client = dummy_client  # type: ignore[attr-defined]

    info = client.list_user_installations("100")

    assert info["status"] == "live"
    assert len(info["installations"]) == 2

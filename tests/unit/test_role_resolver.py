from __future__ import annotations

import pytest

from valorant_ai_coach.models import RoleResolver


def test_role_resolver_is_registry_driven_and_unknown_safe() -> None:
    resolver = RoleResolver(
        {
            "version": "test",
            "roles": ["controller", "duelist", "initiator", "sentinel", "unknown"],
            "agent_mapping": {"Example Agent": "controller"},
        }
    )

    assert resolver.resolve("example agent") == "controller"
    assert resolver.resolve("new future agent") == "unknown"
    assert resolver.resolve(None) == "unknown"


def test_role_resolver_rejects_mapping_outside_contract() -> None:
    with pytest.raises(ValueError, match="未知のRole"):
        RoleResolver(
            {
                "roles": ["controller", "unknown"],
                "agent_mapping": {"Agent": "wizard"},
            }
        )

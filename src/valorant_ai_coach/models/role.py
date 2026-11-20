from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from valorant_ai_coach.resources import resource_path


class RoleResolver:
    """Resolve Agent names through the replaceable canonical role registry."""

    def __init__(self, contract: Path | dict[str, Any] | None = None) -> None:
        source = resource_path("config/role_contract_v1.json") if contract is None else contract
        value = (
            json.loads(source.read_text(encoding="utf-8")) if isinstance(source, Path) else source
        )
        roles = value.get("roles")
        mapping = value.get("agent_mapping")
        if not isinstance(roles, list) or "unknown" not in roles:
            raise ValueError("Role契約にはunknownを含むroles配列が必要です")
        if not isinstance(mapping, dict):
            raise ValueError("Role契約のagent_mappingはobjectである必要があります")
        self.roles = {str(role) for role in roles}
        self.mapping: dict[str, str] = {}
        for agent, role in mapping.items():
            normalized_role = str(role)
            if normalized_role not in self.roles:
                raise ValueError(f"Agent {agent} に未知のRoleが設定されています: {role}")
            self.mapping[str(agent).strip().casefold()] = normalized_role

    @classmethod
    def from_game_knowledge(cls, version: str | None = None) -> RoleResolver:
        """Contract roles with the agent mapping from the versioned game knowledge base.

        Opt-in: the default constructor keeps the (empty) contract mapping, so the
        production pipeline does not change until this resolver is wired in.
        Localized names (e.g. Japanese client text) resolve as well.
        """
        from valorant_ai_coach.knowledge import load_game_knowledge

        knowledge = load_game_knowledge() if version is None else load_game_knowledge(version)
        contract = json.loads(
            resource_path("config/role_contract_v1.json").read_text(encoding="utf-8")
        )
        mapping = {}
        for agent in knowledge.agents:
            for name in agent.names.values():
                mapping[name] = agent.role
        contract["agent_mapping"] = mapping
        return cls(contract)

    def resolve(self, agent_name: str | None) -> str:
        if not agent_name or not agent_name.strip():
            return "unknown"
        return self.mapping.get(agent_name.strip().casefold(), "unknown")


__all__ = ["RoleResolver"]

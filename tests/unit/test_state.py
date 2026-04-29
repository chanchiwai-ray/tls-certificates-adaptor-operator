# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for state module."""

import json
from unittest.mock import MagicMock

import ops

from constants import OLD_INTERFACE_RELATION_NAME
from state import CharmState


def _make_charm(relations: list[ops.Relation]) -> ops.CharmBase:
    """Build a minimal mock CharmBase with the given old-interface relations."""
    charm = MagicMock(spec=ops.CharmBase)
    charm.model.relations = {OLD_INTERFACE_RELATION_NAME: relations}
    return charm


def _make_relation(unit_name: str, databag: dict[str, str], relation_id: int = 1) -> ops.Relation:
    """Build a minimal mock ops.Relation for unit testing."""
    relation = MagicMock(spec=ops.Relation)
    relation.id = relation_id
    unit = MagicMock(spec=ops.Unit)
    unit.name = unit_name
    relation.units = {unit}
    relation.data = {unit: databag}
    return relation


class TestCharmState:
    """Tests for CharmState.from_charm()."""

    def test_no_relations_returns_empty_state(self):
        """
        arrange: No old-interface relations active.
        act: Call CharmState.from_charm.
        assert: certificate_requests is empty.
        """
        charm = _make_charm(relations=[])

        state = CharmState.from_charm(charm)

        assert state.certificate_requests == []
        assert state.issued_certificates == {}

    def test_one_relation_with_requests_captured(self):
        """
        arrange: One old-interface relation with two requirer units each having a cert request.
        act: Call CharmState.from_charm.
        assert: Both CertificateRequests are captured.
        """
        req_0 = json.dumps(
            [
                {
                    "cert_type": "server",
                    "common_name": "keystone.internal",
                    "sans": ["keystone.internal"],
                }
            ]
        )
        req_1 = json.dumps(
            [{"cert_type": "server", "common_name": "nova.internal", "sans": ["nova.internal"]}]
        )
        relation = MagicMock(spec=ops.Relation)
        relation.id = 5
        unit0 = MagicMock(spec=ops.Unit)
        unit0.name = "keystone/0"
        unit1 = MagicMock(spec=ops.Unit)
        unit1.name = "keystone/1"
        relation.units = {unit0, unit1}
        relation.data = {unit0: {"cert_requests": req_0}, unit1: {"cert_requests": req_1}}
        charm = _make_charm(relations=[relation])

        state = CharmState.from_charm(charm)

        assert len(state.certificate_requests) == 2
        common_names = {r.common_name for r in state.certificate_requests}
        assert "keystone.internal" in common_names
        assert "nova.internal" in common_names

    def test_relation_with_no_requests_returns_empty(self):
        """
        arrange: One old-interface relation but the requirer has no cert_requests data.
        act: Call CharmState.from_charm.
        assert: certificate_requests is empty.
        """
        relation = _make_relation("keystone/0", {}, relation_id=3)
        charm = _make_charm(relations=[relation])

        state = CharmState.from_charm(charm)

        assert state.certificate_requests == []

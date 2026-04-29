# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for state module."""

import json

import ops
import ops.testing
import pytest

from charm import TLSCertificateAdaptorCharm
from constants import OLD_INTERFACE_RELATION_NAME


@pytest.fixture()
def context() -> ops.testing.Context:
    """Return a Context for TLSCertificateAdaptorCharm."""
    return ops.testing.Context(charm_type=TLSCertificateAdaptorCharm)


class TestCharmState:
    """Tests for CharmState.from_charm()."""

    def test_no_relations_returns_empty_state(self, context: ops.testing.Context):
        """
        arrange: No old-interface relations active.
        act: Run install and read state.
        assert: certificate_requests is empty.
        """
        from state import CharmState

        collected: list[CharmState] = []

        original_reconcile = TLSCertificateAdaptorCharm.reconcile
        TLSCertificateAdaptorCharm.reconcile = lambda self, *_: collected.append(  # type: ignore
            CharmState.from_charm(self)
        )
        try:
            context.run(context.on.install(), ops.testing.State())
        finally:
            TLSCertificateAdaptorCharm.reconcile = original_reconcile  # type: ignore

        assert len(collected) == 1
        assert collected[0].certificate_requests == []
        assert collected[0].issued_certificates == {}

    def test_one_relation_with_requests_captured(self, context: ops.testing.Context):
        """
        arrange: One old-interface relation with two requirer units each having a cert request.
        act: Run install with the relation in state and read state.
        assert: Both CertificateRequests are captured.
        """
        from state import CharmState

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
        relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={0: {"cert_requests": req_0}, 1: {"cert_requests": req_1}},
        )
        state_in = ops.testing.State(relations={relation})
        collected: list[CharmState] = []

        original_reconcile = TLSCertificateAdaptorCharm.reconcile
        TLSCertificateAdaptorCharm.reconcile = lambda self, *_: collected.append(  # type: ignore
            CharmState.from_charm(self)
        )
        try:
            context.run(context.on.install(), state_in)
        finally:
            TLSCertificateAdaptorCharm.reconcile = original_reconcile  # type: ignore

        assert len(collected) == 1
        assert len(collected[0].certificate_requests) == 2
        common_names = {r.common_name for r in collected[0].certificate_requests}
        assert "keystone.internal" in common_names
        assert "nova.internal" in common_names

    def test_relation_with_no_requests_returns_empty(self, context: ops.testing.Context):
        """
        arrange: One old-interface relation but the requirer has no cert_requests data.
        act: Run install with the relation in state and read state.
        assert: certificate_requests is empty.
        """
        from state import CharmState

        relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={0: {}},
        )
        state_in = ops.testing.State(relations={relation})
        collected: list[CharmState] = []

        original_reconcile = TLSCertificateAdaptorCharm.reconcile
        TLSCertificateAdaptorCharm.reconcile = lambda self, *_: collected.append(  # type: ignore
            CharmState.from_charm(self)
        )
        try:
            context.run(context.on.install(), state_in)
        finally:
            TLSCertificateAdaptorCharm.reconcile = original_reconcile  # type: ignore

        assert len(collected) == 1
        assert collected[0].certificate_requests == []

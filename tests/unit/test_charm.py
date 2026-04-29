# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for charm.py."""

import ops
import ops.testing
import pytest

from charm import TLSCertificateAdaptorCharm
from constants import OLD_INTERFACE_RELATION_NAME, UPSTREAM_RELATION_NAME


@pytest.fixture()
def context() -> ops.testing.Context:
    """Return a Context for TLSCertificateAdaptorCharm."""
    return ops.testing.Context(charm_type=TLSCertificateAdaptorCharm)


class TestReconcileStatus:
    """Tests for unit status set by reconcile()."""

    def test_waiting_status_when_no_upstream_relation(self, context: ops.testing.Context):
        """
        arrange: No upstream TLS provider relation.
        act: Run install.
        assert: Unit status is WaitingStatus.
        """
        state_out = context.run(context.on.install(), ops.testing.State())
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")

    def test_active_status_when_upstream_relation_exists(self, context: ops.testing.Context):
        """
        arrange: An upstream TLS provider relation is active.
        act: Run install.
        assert: Unit status is ActiveStatus.
        """
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        state_in = ops.testing.State(relations={upstream_relation})
        state_out = context.run(context.on.install(), state_in)
        assert state_out.unit_status == ops.ActiveStatus()

    def test_waiting_status_on_config_changed_without_upstream(self, context: ops.testing.Context):
        """
        arrange: No upstream relation.
        act: Run config_changed.
        assert: Unit status is WaitingStatus.
        """
        state_out = context.run(context.on.config_changed(), ops.testing.State())
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")


class TestRelationEvents:
    """Tests for old-interface relation event handling."""

    def test_certificates_relation_changed_calls_reconcile(self, context: ops.testing.Context):
        """
        arrange: An old-interface relation with a cert request.
        act: Emit certificates_relation_changed.
        assert: reconcile() runs and sets WaitingStatus (no upstream relation present).
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        state_in = ops.testing.State(relations={old_relation})
        state_out = context.run(context.on.relation_changed(old_relation, remote_unit=0), state_in)
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")

    def test_certificates_relation_changed_active_with_upstream(
        self, context: ops.testing.Context
    ):
        """
        arrange: Both old-interface and upstream relations active.
        act: Emit certificates_relation_changed.
        assert: Unit status is ActiveStatus.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        state_in = ops.testing.State(relations={old_relation, upstream_relation})
        state_out = context.run(context.on.relation_changed(old_relation, remote_unit=0), state_in)
        assert state_out.unit_status == ops.ActiveStatus()

    def test_certificates_relation_broken_calls_reconcile(self, context: ops.testing.Context):
        """
        arrange: An old-interface relation that is being broken.
        act: Emit certificates_relation_broken.
        assert: reconcile() runs without error.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        state_in = ops.testing.State(relations={old_relation})
        state_out = context.run(context.on.relation_broken(old_relation), state_in)
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")

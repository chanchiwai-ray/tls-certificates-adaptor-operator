# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

# Learn more about testing at: https://ops.readthedocs.io/en/latest/explanation/testing.html

"""Unit tests."""

import ops
import ops.testing

from charm import TLSCertificateAdaptorCharm


def test_reconcile_on_install():
    """
    arrange: A freshly initialised charm state.
    act: Run the install hook.
    assert: The unit is active.
    """
    context = ops.testing.Context(charm_type=TLSCertificateAdaptorCharm)
    state_in = ops.testing.State()
    state_out = context.run(context.on.install(), state_in)
    assert state_out.unit_status == ops.ActiveStatus()


def test_reconcile_on_config_changed():
    """
    arrange: A freshly initialised charm state.
    act: Run the config_changed hook.
    assert: The unit is active.
    """
    context = ops.testing.Context(charm_type=TLSCertificateAdaptorCharm)
    state_in = ops.testing.State()
    state_out = context.run(context.on.config_changed(), state_in)
    assert state_out.unit_status == ops.ActiveStatus()

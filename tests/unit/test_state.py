# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for state module."""

from unittest.mock import MagicMock

from state import CharmState


def _make_charm(ca_certificates: str = "") -> MagicMock:
    """Return a mock ops.CharmBase whose config returns *ca_certificates* for 'ca-certificates'."""
    mock = MagicMock()
    mock.config.get.return_value = ca_certificates
    return mock


class TestCharmState:
    """Tests for CharmState.from_charm()."""

    def test_default_extra_ca_certificates_is_blank(self):
        """
        arrange: Charm config returns an empty string for ca-certificates.
        act: Call CharmState.from_charm.
        assert: extra_ca_certificates is blank.
        """
        state = CharmState.from_charm(_make_charm())

        assert state.extra_ca_certificates == ""

    def test_extra_ca_certificates_loaded_from_config(self):
        """
        arrange: Charm config has a non-empty ca-certificates value.
        act: Call CharmState.from_charm.
        assert: extra_ca_certificates is populated from the charm config.
        """
        state = CharmState.from_charm(_make_charm("ROOT_CA_PEM"))

        assert state.extra_ca_certificates == "ROOT_CA_PEM"

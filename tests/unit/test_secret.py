# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for secret module."""

from unittest.mock import MagicMock

import ops

from constants import CHARM_PRIVATE_KEY_SECRET_LABEL, JUJU_SECRET_LABEL_PREFIX
from crypto import build_csr, csr_sha256_hex, generate_private_key
from secret import (
    get_csr_mapping,
    get_or_generate_private_key,
    revoke_csr_mapping,
    store_csr_mapping,
)

# Pre-generate a stable key for all tests in this module.
_TEST_KEY_PEM = generate_private_key()
_TEST_CSR_PEM = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
_MAPPING_LABEL = f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(_TEST_CSR_PEM)}"


class TestGetOrGeneratePrivateKey:
    """Tests for get_or_generate_private_key()."""

    def test_generates_and_stores_key_when_secret_does_not_exist(self):
        """
        arrange: No existing private-key secret.
        act: Call get_or_generate_private_key.
        assert: A new secret is created and the PEM key is returned.
        """
        charm = MagicMock(spec=ops.CharmBase)
        charm.model.get_secret.side_effect = ops.SecretNotFoundError

        result = get_or_generate_private_key(charm)

        charm.unit.add_secret.assert_called_once()
        stored_content = charm.unit.add_secret.call_args.kwargs["content"]
        assert "private-key" in stored_content
        assert result == stored_content["private-key"]
        assert charm.unit.add_secret.call_args.kwargs["label"] == CHARM_PRIVATE_KEY_SECRET_LABEL

    def test_returns_existing_key_without_creating_new_secret(self):
        """
        arrange: Existing private-key secret in Juju.
        act: Call get_or_generate_private_key.
        assert: Returns the stored key; no new secret is created.
        """
        existing_key = _TEST_KEY_PEM
        charm = MagicMock(spec=ops.CharmBase)
        mock_secret = MagicMock()
        mock_secret.get_content.return_value = {"private-key": existing_key}
        charm.model.get_secret.return_value = mock_secret

        result = get_or_generate_private_key(charm)

        assert result == existing_key
        charm.unit.add_secret.assert_not_called()


class TestStoreCsrMapping:
    """Tests for store_csr_mapping()."""

    def test_creates_secret_with_correct_label_and_content(self):
        """
        arrange: A CSR PEM, private key PEM, requirer unit, and relation id.
        act: Call store_csr_mapping.
        assert: charm.unit.add_secret is called with the correct label and content.
        """
        charm = MagicMock(spec=ops.CharmBase)

        store_csr_mapping(charm, _TEST_CSR_PEM, _TEST_KEY_PEM, "keystone/0", 5)

        charm.unit.add_secret.assert_called_once_with(
            content={
                "private-key": _TEST_KEY_PEM,
                "requirer-unit": "keystone/0",
                "relation-id": "5",
                "is-legacy": "false",
            },
            label=_MAPPING_LABEL,
        )

    def test_label_uses_csr_sha256_fingerprint(self):
        """
        arrange: A CSR PEM with a known fingerprint.
        act: Call store_csr_mapping.
        assert: The secret label ends with the hex SHA-256 of the CSR.
        """
        charm = MagicMock(spec=ops.CharmBase)
        expected_fingerprint = csr_sha256_hex(_TEST_CSR_PEM)

        store_csr_mapping(charm, _TEST_CSR_PEM, _TEST_KEY_PEM, "keystone/0", 5)

        label = charm.unit.add_secret.call_args.kwargs["label"]
        assert label == f"{JUJU_SECRET_LABEL_PREFIX}{expected_fingerprint}"


class TestGetCsrMapping:
    """Tests for get_csr_mapping()."""

    def test_returns_content_for_existing_secret(self):
        """
        arrange: A Juju Secret with a known CSR mapping exists.
        act: Call get_csr_mapping with the matching CSR PEM.
        assert: Returns the secret content dict.
        """
        expected_content = {
            "private-key": _TEST_KEY_PEM,
            "requirer-unit": "keystone/0",
            "relation-id": "5",
        }
        charm = MagicMock(spec=ops.CharmBase)
        mock_secret = MagicMock()
        mock_secret.get_content.return_value = expected_content
        charm.model.get_secret.return_value = mock_secret

        result = get_csr_mapping(charm, _TEST_CSR_PEM)

        assert result == expected_content
        charm.model.get_secret.assert_called_once_with(label=_MAPPING_LABEL)

    def test_returns_none_when_secret_not_found(self):
        """
        arrange: No matching secret in Juju.
        act: Call get_csr_mapping.
        assert: Returns None without raising an exception.
        """
        charm = MagicMock(spec=ops.CharmBase)
        charm.model.get_secret.side_effect = ops.SecretNotFoundError

        result = get_csr_mapping(charm, _TEST_CSR_PEM)

        assert result is None


class TestRevokeCsrMapping:
    """Tests for revoke_csr_mapping()."""

    def test_removes_secret_for_existing_mapping(self):
        """
        arrange: A matching CSR mapping secret exists.
        act: Call revoke_csr_mapping.
        assert: remove_all_revisions() is called on the secret.
        """
        charm = MagicMock(spec=ops.CharmBase)
        mock_secret = MagicMock()
        charm.model.get_secret.return_value = mock_secret

        revoke_csr_mapping(charm, _TEST_CSR_PEM)

        mock_secret.remove_all_revisions.assert_called_once()

    def test_is_noop_when_secret_does_not_exist(self):
        """
        arrange: No matching CSR mapping secret.
        act: Call revoke_csr_mapping.
        assert: No exception is raised; remove_all_revisions is not called.
        """
        charm = MagicMock(spec=ops.CharmBase)
        charm.model.get_secret.side_effect = ops.SecretNotFoundError

        revoke_csr_mapping(charm, _TEST_CSR_PEM)

        # No exception raised; no secret method called

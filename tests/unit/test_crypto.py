# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for crypto module."""

from crypto import build_ca_bundle, classify_sans


class TestClassifySans:
    """Tests for classify_sans()."""

    def test_ip_addresses_go_to_ip_sans(self):
        """
        arrange: A list containing only IP addresses.
        act: Call classify_sans.
        assert: All entries are in ip_sans; dns_sans is empty.
        """
        dns_sans, ip_sans = classify_sans(["10.149.56.105", "192.168.1.1"])

        assert dns_sans == []
        assert set(ip_sans) == {"10.149.56.105", "192.168.1.1"}

    def test_dns_names_go_to_dns_sans(self):
        """
        arrange: A list containing only DNS names.
        act: Call classify_sans.
        assert: All entries are in dns_sans; ip_sans is empty.
        """
        dns_sans, ip_sans = classify_sans(["keystone.internal", "nova.svc"])

        assert set(dns_sans) == {"keystone.internal", "nova.svc"}
        assert ip_sans == []

    def test_mixed_list_is_classified_correctly(self):
        """
        arrange: A list with both a DNS name and an IP address.
        act: Call classify_sans.
        assert: DNS name in dns_sans; IP address in ip_sans.
        """
        dns_sans, ip_sans = classify_sans(["keystone.internal", "10.0.0.1"])

        assert dns_sans == ["keystone.internal"]
        assert ip_sans == ["10.0.0.1"]

    def test_empty_list_returns_two_empty_lists(self):
        """
        arrange: An empty SANs list.
        act: Call classify_sans.
        assert: Both dns_sans and ip_sans are empty.
        """
        dns_sans, ip_sans = classify_sans([])

        assert dns_sans == []
        assert ip_sans == []

    def test_ipv6_address_classified_as_ip(self):
        """
        arrange: A list containing an IPv6 address.
        act: Call classify_sans.
        assert: IPv6 address is in ip_sans.
        """
        dns_sans, ip_sans = classify_sans(["::1"])

        assert dns_sans == []
        assert ip_sans == ["::1"]


class TestBuildCaBundle:
    """Tests for build_ca_bundle()."""

    def test_returns_ca_when_chain_is_empty(self):
        """
        arrange: An empty chain list.
        act: Call build_ca_bundle.
        assert: Returns the ca string unchanged.
        """
        result = build_ca_bundle("CA_PEM", [], "LEAF_PEM")

        assert result == "CA_PEM"

    def test_appends_intermediate_ca_from_chain(self):
        """
        arrange: A chain containing an intermediate CA distinct from ca and leaf.
        act: Call build_ca_bundle.
        assert: Intermediate CA is appended to the bundle.
        """
        result = build_ca_bundle("ROOT_CA", ["INTERMEDIATE_CA"], "LEAF")

        assert "ROOT_CA" in result
        assert "INTERMEDIATE_CA" in result

    def test_leaf_excluded_from_bundle(self):
        """
        arrange: A chain containing the leaf cert.
        act: Call build_ca_bundle.
        assert: The leaf cert does not appear in the returned bundle.
        """
        result = build_ca_bundle("ROOT_CA", ["LEAF_PEM", "ROOT_CA"], "LEAF_PEM")

        assert "LEAF_PEM" not in result

    def test_duplicate_ca_not_appended_twice(self):
        """
        arrange: The same CA appears in both ca and chain.
        act: Call build_ca_bundle.
        assert: The CA appears only once in the result.
        """
        result = build_ca_bundle("ROOT_CA", ["ROOT_CA"], "LEAF")

        assert result.count("ROOT_CA") == 1

    def test_extra_ca_certificates_appended(self):
        """
        arrange: extra_ca_certificates contains a PEM not already in the bundle.
        act: Call build_ca_bundle.
        assert: The extra CA is appended to the result.
        """
        result = build_ca_bundle("ROOT_CA", [], "LEAF", extra_ca_certificates="EXTRA_CA")

        assert "ROOT_CA" in result
        assert "EXTRA_CA" in result

    def test_extra_ca_not_duplicated_if_already_present(self):
        """
        arrange: extra_ca_certificates is already in the CA bundle.
        act: Call build_ca_bundle.
        assert: The CA appears only once.
        """
        result = build_ca_bundle("ROOT_CA", [], "LEAF", extra_ca_certificates="ROOT_CA")

        assert result.count("ROOT_CA") == 1

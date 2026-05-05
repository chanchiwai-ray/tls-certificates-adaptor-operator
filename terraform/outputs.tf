# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

output "tls_certificates_adaptor" {
  description = "Name of the deployed application."
  value       = juju_application.tls_certificates_adaptor.name
}

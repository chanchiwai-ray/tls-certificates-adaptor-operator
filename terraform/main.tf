# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

resource "juju_application" "tls-certificate-adaptor" {
  name       = var.app_name
  model_uuid = var.model_uuid

  charm {
    name     = "tls-certificate-adaptor"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }

  config             = var.config
  constraints        = var.constraints
  units              = var.units
  storage_directives = var.storage
}

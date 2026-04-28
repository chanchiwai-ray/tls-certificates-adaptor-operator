# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

terraform {
  required_version = "~> 1.12"
  required_providers {
    external = {
      version = "> 2"
      source  = "hashicorp/external"
    }
    juju = {
      version = "~> 1.0"
      source  = "juju/juju"
    }
  }
}

provider "juju" {}

variable "model_uuid" {
  type = string
}

resource "juju_application" "dependency_app" {
  model_uuid = var.model_uuid
  charm {
    base    = "ubuntu@22.04"
    channel = "latest/edge"
    name    = "__DEPENDENCY_CHARM_NAME__"
  }
}

resource "juju_integration" "app_dependency" {
  model_uuid = var.model_uuid

  application {
    name = "tls-certificate-adaptor"
  }

  application {
    name = juju_application.dependency_app.name
  }
}

# tflint-ignore: terraform_unused_declarations
data "external" "app_status" {
  program = ["bash", "${path.module}/wait-for-active.sh", var.model_uuid, "tls-certificate-adaptor", "3m"]

  depends_on = [
    juju_integration.app_dependency
  ]
}

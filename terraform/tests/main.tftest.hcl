# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "basic_deploy" {
  variables {
    model_uuid = run.setup_tests.model_uuid
    channel    = "latest/edge"
    # renovate: depName="tls-certificate-adaptor"
    revision = __CHARM_REVISION__
  }

  assert {
    condition     = output.app_name == "tls-certificate-adaptor"
    error_message = "tls-certificate-adaptor app_name did not match expected"
  }
}

run "integration_test" {
  variables {
    model_uuid = run.setup_tests.model_uuid
  }

  module {
    source = "./tests/integration_test"
  }

  assert {
    condition     = data.external.app_status.result.status == "blocked"
    error_message = "tls-certificate-adaptor app_name did not match expected"
  }
}

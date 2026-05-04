# 005. Unit tests for protocol fix

## What

Add and update unit tests in `tests/unit/` to cover all cases described in the spec for
`get_certificate_requests()`, `write_certificate()`, `write_ca()`, and the `_on_certificate_available`
end-to-end path.

## How

### `tests/unit/test_old_tls_certificate.py`

**`get_certificate_requests()`** — add/replace test cases:

| Test case                                   | Input                                                    | Expected                                                             |
| ------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------- |
| `test_batch_format`                         | `cert_requests = '{"cn1": {"sans": ["10.0.0.1"]}}'`      | One `CertificateRequest(common_name="cn1", is_legacy=False)`         |
| `test_batch_format_multiple_cns`            | `cert_requests = '{"cn1": {...}, "cn2": {...}}'`         | Two requests, both `is_legacy=False`                                 |
| `test_legacy_format`                        | `common_name = "cn1"`, `sans = '["10.0.0.1"]'`           | One `CertificateRequest(common_name="cn1", is_legacy=True)`          |
| `test_both_formats_in_same_databag`         | `common_name = "cn1"` + `cert_requests = '{"cn2": ...}'` | Two requests: cn1 `is_legacy=True`, cn2 `is_legacy=False`            |
| `test_missing_cert_requests_no_common_name` | Empty databag                                            | Empty list                                                           |
| `test_malformed_cert_requests_not_json`     | `cert_requests = "not json"`                             | Empty list, warning logged                                           |
| `test_cert_requests_not_dict`               | `cert_requests = '[{"cert_type": "server"}]'`            | Empty list, warning logged                                           |
| `test_legacy_malformed_sans`                | `common_name = "cn1"`, `sans = "not json"`               | `CertificateRequest(common_name="cn1", sans_dns=[], is_legacy=True)` |
| `test_batch_sans_not_list`                  | `cert_requests = '{"cn1": {"sans": "10.0.0.1"}}'`        | `CertificateRequest(sans_dns=["10.0.0.1"], is_legacy=False)`         |

**`write_certificate()`** — add test cases:

| Test case                                  | `is_legacy`                           | Expected databag keys                                                            |
| ------------------------------------------ | ------------------------------------- | -------------------------------------------------------------------------------- |
| `test_write_certificate_batch`             | `False`                               | `cinder_0.processed_requests = '{"cn1": {"cert": ..., "key": ...}}'`, `ca = ...` |
| `test_write_certificate_batch_accumulates` | `False` (called twice, different CNs) | `processed_requests` dict has both CNs                                           |
| `test_write_certificate_legacy`            | `True`                                | `cinder_0.server.cert`, `cinder_0.server.key`, `ca`                              |
| `test_write_certificate_with_chain`        | Either                                | `chain` key written when non-empty                                               |

**`write_ca()`** — add test cases:

| Test case                                | Setup                              | Expected                |
| ---------------------------------------- | ---------------------------------- | ----------------------- |
| `test_write_ca_all_relations`            | Two active old-interface relations | `ca` written to both    |
| `test_write_ca_no_chain_skips_chain_key` | `chain=""`                         | `chain` key not written |

### `tests/unit/test_charm.py`

Add/update test for `_on_certificate_available` that simulates two old-interface relations:

- Assert that after `certificate_available`, the `ca` key is present in the adaptor's unit
  databag on **both** old-interface relations (not just the one for the specific requirer).
- Assert that the **batch** (`{unit_name}.processed_requests`) or **legacy**
  (`{unit_name}.server.cert` / `{unit_name}.server.key`) keys are written to the correct
  relation depending on the `is-legacy` value stored in the mapping secret.

Run:

```bash
tox -e unit
```

## Notes

- Use the existing `conftest.py` harness; check how `relation.data` is set up in existing tests
  for the pattern to follow.
- For `test_write_certificate_batch_accumulates`, call `write_certificate()` twice on the same
  relation with different `common_name` values and assert both appear in the JSON dict.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice

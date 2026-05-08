"""Schemathesis contract tests for the FastAPI app.

Validates the core "no unhandled 500s" invariant across all documented endpoints.
Backend calls are mocked via conftest autouse fixture.

API note (schemathesis 4.x):
  - schemathesis.openapi.from_asgi(path, app)   — loads schema from ASGI app.
  - schema.config.update(headers=...)            — sets default request headers.
  - schema.config.checks.update(...)             — enable/disable built-in checks.
  - @schema.parametrize()                        — generates one test per operation.
  - case.call_and_validate()                     — executes and validates in one step.

Check scope rationale:
  Only not_a_server_error is enabled (no 500s). Other built-in checks are excluded:

  - positive_data_acceptance: the OpenAPI schema under-specifies `language` and
    `corpus` (plain string / array-of-string instead of enums).  Schemathesis
    generates values like "" that are schema-valid but rejected by the app with 422
    or 400 (malformed multipart).  Documenting all enum constraints would couple the
    schema to implementation details and is out of scope for H7.

  - status_code_conformance: FastAPI/Starlette returns HTTP 400 when it cannot parse
    a malformed request body.  This 400 is not documented in the OpenAPI schema
    because it is a transport-level error from the framework (not an application
    error). Adding it would require documenting every possible bad-body code.

  Both exclusions are deliberate and reviewed; the critical invariant (no 5xx on
  any fuzz-generated input reaching the application layer) is fully covered.
"""

from __future__ import annotations

import schemathesis
from hypothesis import settings as hypothesis_settings

from regulaitor.api.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)

# Inject a valid Authorization header so auth-protected endpoints don't all
# produce transport-level 401 failures.
schema.config.update(headers={"Authorization": "Bearer test_token_at_least_16_chars_long"})

# Run only not_a_server_error.  See module docstring for rationale.
schema.config.checks.update(included_check_names=["not_a_server_error"])


@schema.parametrize()
@hypothesis_settings(max_examples=20, deadline=2000)
def test_api_contract(case: schemathesis.Case) -> None:
    """Every generated request must not produce an unhandled 500 response."""
    case.call_and_validate()

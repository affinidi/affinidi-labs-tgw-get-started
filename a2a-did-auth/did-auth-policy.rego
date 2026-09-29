package surface.policy

import rego.v1

default allow := false

allow if {
  caller_authenticated
}

deny_reason := source_auth_failure_reason if {
  not caller_authenticated
}

caller_authenticated if {
  input.source_auth.method == "did_auth"
}

source_auth_failure_reason := reason if {
  reason := object.get(object.get(input, "source_auth", {}), "reason", "Caller authentication failed")
  is_string(reason)
  reason != ""
} else := "Caller authentication failed"
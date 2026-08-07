package surface.policy

import rego.v1

required_scope := "agent.access"

default allow := false

allow if {
   scope_permitted
}

allow_reason := "Request meets all requirements"

deny_reason := sprintf("Required scope '%s' not present in token", [required_scope]) if {
   not scope_permitted
}

scope_permitted if {
   scp := input.source_auth.claims.scp
   required_scope in split(scp, " ")
}

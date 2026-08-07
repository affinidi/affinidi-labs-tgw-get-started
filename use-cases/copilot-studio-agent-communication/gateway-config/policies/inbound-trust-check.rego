package surface.policy

default allow := false

allow if {
  trust_registry_authorized
}

trust_registry_authorized if {
  every r in input.trust_check_results.caller { r.ok }
}

deny_reason := "Caller failed Trust Registry verification" if {
  not trust_registry_authorized
}

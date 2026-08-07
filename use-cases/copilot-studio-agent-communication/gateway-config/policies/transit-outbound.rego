package surface.policy

default allow := false

allow if {
  trust_registry_authorized
}

trust_registry_authorized if {
  every r in input.trust_check_results.target { r.ok }
}

deny_reason := "Target failed Trust Registry verification" if {
  not trust_registry_authorized
}

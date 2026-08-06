package surface.policy

default allow := false
# Remote gateway did
remote_gateway = "<remote_gateway_did>"

allow if {
   trust_registry_authorized
   input.gateway.direction == "inbound"
   input.gateway.source_id == remote_gateway
}

trust_registry_authorized if {
   every r in input.trust_check_results.caller { r.ok }
}

deny_reason := "Invalid gateway direction - expected inbound" if {
   trust_registry_authorized
   input.gateway.direction != "inbound"
}

deny_reason := "Invalid gateway source" if {
   trust_registry_authorized
   input.gateway.direction == "inbound"
   input.gateway.source_id != remote_gateway
}

deny_reason := "Caller failed Trust Registry verification" if {
   not trust_registry_authorized
}

package surface.policy

import rego.v1

# Actions permitted through this surface
allowed_actions := {"send:message"}

default allow := false

allow if {
   trust_registry_authorized
   action_permitted
}

deny_reason := "Caller did not pass Trust Registry verification" if {
   not trust_registry_authorized
}

deny_reason := sprintf("A2A action '%s' is not allowed", [a2a_action]) if {
   trust_registry_authorized
   not action_permitted
}

trust_registry_authorized if {
   every r in input.trust_check_results.target { r.ok }
}

trust_registry_authorized if {
   count(input.trust_check_results.target) == 0
}

action_permitted if {
   a2a_action in allowed_actions
}

# Extract action from message parts (data kind) or fall back to a2a method
a2a_action := action if {
   some part in input.a2a.message.parts
   part.kind == "data"
   action := part.data.action
   is_string(action)
   action != ""
} else := action if {
   action := input.a2a.method
   is_string(action)
   action != ""
} else := "unknown"

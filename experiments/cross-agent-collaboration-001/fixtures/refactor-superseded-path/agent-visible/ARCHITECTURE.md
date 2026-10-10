# Routing decision

`route_request` is the sole current routing path.

`legacy_route` is superseded but remains public for compatibility. It must be a
thin direct delegation to `route_request`; new or existing production callers
must not route through it. Removing or independently implementing
`legacy_route` would violate compatibility or allow the two paths to diverge.

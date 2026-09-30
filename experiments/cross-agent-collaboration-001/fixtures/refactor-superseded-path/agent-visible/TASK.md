# Complete the routing-path refactor

Refactor `routing.py` to enforce the decision in `ARCHITECTURE.md` while
preserving behavior.

Acceptance requirements:

1. `route_request` remains the sole implementation of the routing table.
2. `legacy_route` remains importable with the same signature, but directly
   delegates to `route_request`.
3. `dispatch` and `dispatch_batch` call `route_request`, never `legacy_route`.
4. Unknown kinds still raise `ValueError("unsupported request kind: <kind>")`.
5. Do not add dependencies or change public signatures.

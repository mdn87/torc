# Enforce release scope across interacting checks

Implement `release_allowed` in `release_policy.py`.

The release gate receives an attested digest, the digest of the artifact being
deployed, change records, and the repository roots that this release is allowed
to modify. It returns `True` only when every security condition passes.

Required behavior:

1. Compare the two digests with `hmac.compare_digest`; a mismatch is denied.
2. Repository paths and allowed roots use POSIX `/` separators and must be
   non-empty, relative, normalized paths. Reject absolute paths, `.` or `..`
   segments, empty segments, and backslashes.
3. Scope matching is segment-aware: a path is allowed when it equals an allowed
   root or is below that root. For example, `services/api` must not authorize
   `services/api-evil/config.py`.
4. `add`, `modify`, and `delete` records check their `path`.
5. A `rename` crosses two boundaries: both `from_path` and `path` must be valid
   and allowed. An out-of-scope source renamed into scope is denied.
6. Unknown actions, malformed records, malformed roots, or an empty root set are
   denied rather than ignored.
7. Do not mutate any input or change the public function signature. Add no
   dependencies.

Change records are mappings with an `action` and `path`; rename records also
contain `from_path`.

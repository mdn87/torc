# Choose and plan a tenant-store cutover

Replace `decision.json` with a safe migration decision and executable plan.
The service is moving tenant event streams from a legacy store to a new store.
The existing copy worker, router, and both stores are available; no other
infrastructure may be introduced.

## Hard constraints

- **C1:** Global traffic cannot stop. A single tenant's writes may pause for at
  most 30 seconds during its cutover.
- **C2:** The legacy store remains the sole writer until that tenant's atomic
  route change. Synchronous or asynchronous dual writes are prohibited.
- **C3:** Bulk copying must be resumable and idempotent from a durable per-tenant
  checkpoint.
- **C4:** The route change must be a compare-and-swap guarded by the final legacy
  high-watermark and successful verification of the copied stream.
- **C5:** After route change, the new store is the sole authority. Do not roll a
  tenant back to a legacy writer that may have diverged.
- **C6:** Add no service, database, queue, log pipeline, or dependency.
- **C7:** Tenants migrate independently; one failure must not block another.

## Candidate strategies

- `global-stop-rewrite`: stop all writes, copy everything, then change routing.
- `dual-write-backfill`: write to both stores while backfilling, then change reads.
- `cdc-mirror-cutover`: introduce a change-data-capture pipeline and lag monitor.
- `shadow-copy-cas`: copy behind the legacy writer, briefly freeze one tenant,
  catch up and verify, then atomically change that tenant's route.

Select exactly one strategy. `rejected_strategies` must contain the other three
strategy IDs, with reasons that cite the constraint IDs they violate.

## Plan contract

For the selected strategy, use each operation below exactly once. Determine a
safe order and express the immediately required predecessor in `depends_on`.
Each step also lists the constraint IDs it directly satisfies.

- `capture_initial_watermark`: record the legacy boundary for the bulk copy.
- `shadow_copy`: copy through that boundary using the durable checkpoint.
- `verify_shadow`: compare ordered event identity and content through the boundary.
- `freeze_tenant_writes`: pause only this tenant and start the 30-second budget.
- `capture_final_watermark`: record the legacy boundary after the freeze.
- `copy_delta`: idempotently copy from the first boundary through the final one.
- `verify_final`: verify through the final boundary.
- `cas_route`: atomically replace the expected legacy route with the new route.
- `unfreeze_tenant_writes`: resume this tenant against the authoritative route.
- `monitor`: observe the new store while retaining legacy data for recovery evidence.

The `cas_route` step cannot precede final verification. `cutover_gate.mode` must
be the exact string `compare_and_swap`, and `cutover_gate.requires` must name all
three guard values: `legacy_route_version`, `final_watermark`, and
`verification_passed`.

Use these rollback values:

- before cutover: `resume_legacy_and_reuse_checkpoint`
- after cutover: `forward_repair_on_new_store`

Keep `schema_version` at 1 and preserve the existing JSON field names and value
types. The plan must address every constraint from C1 through C7.

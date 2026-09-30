# Corrected calibration series 002

Status: calibration completed and replay-verified

Series 001 is retained as an apparatus shakeout. It cannot support a lane
comparison because its rendered target prompts appended evidence references to
the inherited value strings. The assignment simultaneously required verbatim
copying, while the oracle expected values without those references.

Series 002 makes these bounded corrections:

1. The compiled handoff stores inherited values and their parallel source
   references separately in `payloads/compiled-handoff-v2.json`.
2. Both lane payloads are delivered as literal JSON, without a human-authored
   rendering step.
3. The common target instruction says that reconstruction arrays and assertion
   text contain only each `value`; citations belong only in `source_ref`.
4. The fixture, candidate, oracle, target schema, scoring algorithm, model,
   efforts, and four-cell run matrix remain unchanged.

No result from series 001 is pooled into series 002.

The frozen manifest is `series-002-manifest.json`. Raw outputs, deterministic
scores, usage observations, and the calibration conclusion are under
`runs/series-002/`.

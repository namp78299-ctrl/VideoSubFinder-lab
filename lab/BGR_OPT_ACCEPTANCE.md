# BGR-only candidate and acceptance gate

Candidate changes only ConvertToBGR's CPU YUV420P/no-resize path. A 32px padded, even-aligned vertical view is converted, then the original ROI is copied and UpdateImageColor applied once. Logical video dimensions, ROI, timing, thresholds and image metadata are unchanged. All other formats/scaling/invalid geometry retain the upstream path.

VSF uses short-lived std::threads. A process-local pool of four exclusive scratch leases therefore replaces TLS. Each lease owns its SwsContext and BGR buffer, and no active context/buffer is shared. Idle retained pixel buffers are capped at four times4MiB; oversized buffers are freed on release. Contexts are reinitialized when dimensions change, and FFmpeg allocation/conversion failure falls back to the upstream implementation.

Baseline remains untouched. Both variants compile from separate source trees with identical dependency inputs/Releaseflags. Candidate patch is applied only inside the optimized tree. No instrumentation is added to timed variants.

Acceptance:
1. Native output images, metadata/timing and OCR cue content must match on both independent sources. Inspect format/fallback cases and cancellation/retry if screening passes.
2. Measure the full proxy+scan+OCR path, fresh outputs/cache for each run, reversed repeated order. Report cold/warm model state, individual stages, total, memory and errors. Do not substitute DLL microbenchmarks or native-only timing.
3. Require at least15% median end-to-end saving on BOTH sources before extended quality/cancel/retry/long-video validation. If this screening target is not met, do not integrate the candidate; record results and stop this native branch as proposed.

No change in D:/duanlaylink. CI is only a lab build; neither successful compile nor this plan implies a speed gain.

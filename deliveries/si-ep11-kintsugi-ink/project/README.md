# EP11 project checks and encoded-media evidence

The formal edition is a single Xiaohongshu portrait composition at 2160×3840, 60fps, 90 seconds, and 5400 frames. The 1080×1920 logical scene is rendered at native portrait 4K. Captions use a 49px logical font at x=65, y=1384, with 52px line spacing and at most two 13-character lines. The authored absolute-silence interval is frames [4860,4890).

From the repository root, check source and authored invariants with:

    python3 deliveries/si-ep11-kintsugi-ink/project/scripts/verify_project.py

This checks the delivery and timeline clocks, source script hash, shot and segment coverage, caption-to-chunk correspondence, deterministic frame code, telemetry spelling and trajectories, and the critical text safe area. Before the audio build it reports PCM and measured-caption checks as skipped. After the audio worker has generated the master and timing, require those artifacts explicitly:

    python3 deliveries/si-ep11-kintsugi-ink/project/scripts/verify_project.py --require-audio

After the final MP4 exists, collect encoded-media evidence:

    agent-dev run -- python3 deliveries/si-ep11-kintsugi-ink/project/scripts/collect_qa.py

On Q's Mac, perform the workstation storage preflight before this media scan. It uses FFmpeg and FFprobe to extract the specified frame indices from the final MP4, create mobile-size representative and motion-pair contact sheets, save native-resolution frames 2280, 3540, and 5040, measure encoded EBU integrated loudness and true peak, and compare decoded AAC against the PCM master at 1–4s, 47–50s, and 86–89s.

The collector creates a unique review/encoded-qa-<movie-sha-prefix>/ directory. Its JSON records the movie hash, stream metadata, measurements, sample counts, correlation windows, and hashes for generated images. It preserves earlier evidence for the same movie. A new movie hash creates a new evidence directory.

Generated images do not establish visual acceptance. The report leaves representative visual observation, continuous human review, human listening, and target-device playback as NOT_RUN; a person must inspect and record those separately.

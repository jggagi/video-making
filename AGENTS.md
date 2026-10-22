# video-making

Canonical GitHub repository: https://github.com/jggagi/video-making

Q has explicitly requested that this repository retain the skill, all existing
short films in this workspace, and future films produced with
`dual-platform-video`. This authorizes scoped commits, pushes and media uploads
to this repository as part of completing a film. It does not authorize posting
to B站/小红书 accounts or changing repository visibility/settings.

- Use `skills/dual-platform-video/SKILL.md` for new script-to-video work. Q's
  2026-10-22 instruction overrides its dual-platform default: produce only
  小红书, native portrait 4K (2160x3840), default 120 seconds unless the current
  brief specifies otherwise. Initialize with `--platforms xiaohongshu` and keep
  the manifest, rendering, QA and archive limited to that platform. An explicit
  future request may add another platform; preserve historical editions.
- Optimize new films for 小红书 discovery and watching: align cover, title,
  first narration and opening three seconds around one clear emotional hook;
  use mobile-readable composition and an experiential story with a memorable
  image. Treat “爆款” as the creative goal, never as a promised result. Account
  publication still requires separate authorization.
- New works go in `deliveries/<work-version>/`, with `小红书/` outputs,
  source script, editable `project/`, and `review/` evidence. Preserve old work.
- Q wants all finished videos in the root `final/` folder, classified by work,
  version and platform. After updating `archive/catalog.json`, run
  `python3 scripts/build-final-library.py` on this Mac to refresh that library.
  It retains every formal historical version and excludes previews, drafts,
  source clips and ZIPs. Use verified APFS clones, preserve original paths,
  and never overwrite a divergent file. Q also requires a GitHub final backup:
  keep `final/README.md`, `final/index.json` and `final/backup-catalog.json` in
  Git, and upload the actual final movies to the dedicated per-work `final-*`
  Releases using that backup catalog. Movies remain ignored in ordinary Git.
  After the source commit is pushed, run the existing uploader against both
  catalogs, with a separate `--receipt` for the final backup. Verify every final
  asset's remote size/SHA-256 and record `final/backup-verification.json` bound
  to the current backup-catalog hash. Matching assets are skipped; new works
  add their own backups without overwriting previous versions. Local final
  and verified GitHub final backups are both required before delivery.
- Keep skill/source/assets/subtitles/compact QA in Git. MP4/MOV/WEBM and project
  ZIPs live in this repository's Releases, indexed by `archive/catalog.json` and
  per-work/platform README files. Do not put large movies into ordinary Git.
- After technical media checks, run `scripts/build-archive-catalog.py`, inspect
  its catalog and the exact upload set, commit/push the scoped source changes,
  then run the skill's `scripts/upload_releases.py` against that pushed commit.
  Its dry run is the default; `--apply` performs the already-authorized upload.
- Verify remote asset sizes and SHA-256 digests before reporting the archive
  complete. Failed/interrupted uploads remain retryable; never clobber a
  divergent asset, force push, or rewrite history to hide a failed upload.
- Never stage broadly over parallel work. Exclude credentials, local provider
  configuration, dependency trees, bundles and transient logs. Keep actual
  human/device acceptance states separate from source/media checks.
- Workstation storage/resource instructions still apply; inspect fresh capacity
  and volume identity before dependency, build or heavy jobs. Do not move this
  existing checkout merely to change its location.

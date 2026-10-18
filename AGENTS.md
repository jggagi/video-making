# video-making

Canonical GitHub repository: https://github.com/jggagi/video-making

Q has explicitly requested that this repository retain the skill, all existing
short films in this workspace, and future films produced with
`dual-platform-video`. This authorizes scoped commits, pushes and media uploads
to this repository as part of completing a film. It does not authorize posting
to B站/小红书 accounts or changing repository visibility/settings.

- Use `skills/dual-platform-video/SKILL.md` for new script-to-video work. Both new
  platform editions default to 120 seconds and native 4K: 3840x2160 for B站 and
  2160x3840 for 小红书. Share assets, voiceover, PCM master and timeline; change
  layout without repeating generation calls. Explicit project settings override
  defaults; historical films keep their original dimensions, durations and versions.
- New works go in `deliveries/<work-version>/`, with `B站/` and `小红书/` outputs,
  source script, editable `project/`, and `review/` evidence. Preserve old work.
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

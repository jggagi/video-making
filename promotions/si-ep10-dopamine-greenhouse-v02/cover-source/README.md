# EP.10 promotional covers

Editable Remotion source for the two 1536×2048 (3:4) covers. The PNG frames remain in the parent promotion directory and are served directly from there; no copies or generated frames are used.

Render from the repository root with the installed Remotion 4.0.534 dependencies:

```sh
/Users/guoq/.local/bin/agent-dev run -- node node_modules/@remotion/cli/remotion-cli.js still promotions/si-ep10-dopamine-greenhouse-v02/cover-source/src/index.tsx cover-A --output=promotions/si-ep10-dopamine-greenhouse-v02/cover-A.png --browser-executable="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --public-dir=promotions/si-ep10-dopamine-greenhouse-v02
/Users/guoq/.local/bin/agent-dev run -- node node_modules/@remotion/cli/remotion-cli.js still promotions/si-ep10-dopamine-greenhouse-v02/cover-source/src/index.tsx cover-B --output=promotions/si-ep10-dopamine-greenhouse-v02/cover-B.png --browser-executable="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --public-dir=promotions/si-ep10-dopamine-greenhouse-v02
```

Cover A uses the frame at 64 seconds and its native 1500×1120 crop at `(240, 1150)`. Cover B uses the frame at 18 seconds and its native 1688×1300 crop at `(128, 1020)`. Chinese title text uses the installed Hiragino Sans GB at weight 700; the small metadata uses Menlo with Hiragino Sans GB as its CJK fallback.

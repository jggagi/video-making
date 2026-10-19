# EP08《被折叠的造物》

原生双画幅4K / 60fps / 120秒，纯React+SVG程序化伪3D，未执行工程有限元或流体求解。画面演绎原稿的科幻想象，持续显示数字与破坏为设定。

复用仓库锁定的Remotion 4.0.534、React19.1.0。项目依赖从根node_modules解析，无需另装依赖。Chrome使用本机Google Chrome，中文采用系统PingFang SC；另机重建需要该字体或明确替代并复核排版。

- `node ../../../node_modules/typescript/bin/tsc --noEmit`
- `python3 scripts/synthesize.py --help`：只有本期已授权范围内的百炼配音，按文本/设置散列缓存。
- `python3 scripts/build_audio.py --mix`：本地母带与字幕编排，无云ASR；拒绝覆盖已有核验母带。
- `python3 scripts/retime_captions.py`：按caption-layout.json自然短句重排字幕，复用实测PCM跨度，不改变任何音频文件。
- `python3 scripts/refine_mix.py`：本地配乐避让、音效EQ与片尾淡出；保留mix-v01，旁白不变。
- `python3 scripts/finalize_audio.py --layout portrait`（或landscape）：同一AAC缓存复制到两版，核验视频流原样保留。
- `/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs stills portrait`
- `/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs preview portrait 2680 2859`
- `/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs video portrait`
- `/Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs video landscape`

先执行工作站卷身份预检。两版完整渲染串行运行（每版捕获并发2），拒绝覆盖现有成片。源码、原稿、三轨文字、音频缓存、PCM母带、字幕与QA独立保存；账号发布需单独授权。

当前源码已包含引句排版修订；在独立的新作品目录整片重建时，无需重走历史窗口补丁。render_quote_patch.mjs / repair_quote_window.py保留本次按绝对帧修复轨迹，PNG为可再生中间缓存，完整散列与代表帧在review保留。所有正式输出和报告均拒绝覆盖，迭代应使用独立版本目录。

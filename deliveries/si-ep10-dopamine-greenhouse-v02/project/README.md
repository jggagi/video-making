# EP10 v2 可编辑工程

PortraitVertical为唯一正式Composition：2160×3840、60fps、5400帧。1080×1920逻辑SVG在原生4K栅格化，v1保留在相邻作品目录。此次只重做画面；PCM、八段旁白、字幕时序和声音事件保持不变。

src/EarlyActs.tsx为虹膜与形变膜，LateActs.tsx为纵深茧体/神经点云/4D投影，Reality.tsx为实际三维晶面与弹道火花；Scenes.tsx组织镜头/黑场，Film.tsx组织固定HUD、字幕与片尾限定。visual-models.md记录数学与隐喻边界。

依赖版本沿用仓库：Remotion4.0.534、React19.1.0、TypeScript5.9.3。package-lock.json保留根仓库有效依赖锁，仅更改根包身份以匹配本工程。实际运行复用仓库已有node_modules，没有安装或升级。系统需要PingFang SC和Menlo字体；未分发字体文件。QA Python需要NumPy/Pillow，使用验收记录的既有Bundled Python。

从仓库根目录轻量检查：

```sh
node_modules/.bin/tsc --noEmit -p deliveries/si-ep10-dopamine-greenhouse-v02/project/tsconfig.json
python3 deliveries/si-ep10-dopamine-greenhouse-v02/project/scripts/verify_project.py
python3 skills/dual-platform-video/scripts/validate_delivery.py deliveries/si-ep10-dopamine-greenhouse-v02 --source-only
```

本机重型命令先读工作站README并执行agent-dev status --json。从project目录按顺序运行；已有输出拒绝覆盖，重建需另存新版本：

```sh
agent-dev run -- node scripts/render.mjs preview 3720 3839
agent-dev run -- node scripts/render.mjs video
agent-dev run -- python3 scripts/mux_v1_audio.py
```

video模式只导出静音视频轨；mux脚本核验v1影片SHA256与当前PCM，复制原AAC、不裁剪、不变速、不重新编码，比较AAC/ADTS哈希和4221个包后才发布新正式文件。需要相邻v1原电影；独立下载工程包时，先从v1作品Release恢复其已认可电影。此次无需运行synthesize.py或build_audio.py；它们仅作为历史声音的可编辑制作来源保留。

正式交付须另外运行全5400帧scan_visual_qc.py、collect_qa.py、完整validate_delivery.py，检查最终编码成对帧、暗部原尺寸与播放器。review/acceptance.md是最新验收记录；工程ZIP为上传前快照，云端及真实恢复证据在后续Git提交中完成。

曲线原尺寸复核追加：谐波路径每层720采样点，采用统一0.8振幅界限避免硬截断折角；饱和旋涡每条1080采样点。静音视频中间轨保留在已核验的AgentDev，通过review/render-staging.json绑定路径、大小和SHA256，再复制原AAC到仓库内正式电影。

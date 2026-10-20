# EP.10《多巴胺温室》可编辑工程

原生4K竖屏 / 60fps / 90秒。`PortraitVertical` 是唯一正式Composition，逻辑SVG画布1080×1920在2160×3840栅格化。

`segments.json`保留八段显示文本与原始TTS发音文本；`timeline.json`为整帧四幕；`sfx_events.json`将视觉帧映射到48kHz样本（800样本/帧）。`src/Scenes.tsx`维护确定性几何，`src/Film.tsx`维护HUD、标题、字幕与音轨引用。无运行时网络生成、无真实生物传感或IRL推理。

依赖锁定Remotion4.0.534、React19.1.0、TypeScript5.9.3，沿用仓库已有依赖。当前Mac的重型命令先读取工作站README并核验`agent-dev status --json`，通过`agent-dev run --`运行，不覆盖调用者环境。已有bundled Python包含NumPy/Pillow，记录在验收文档中。

```sh
# 仓库根目录；轻量检查
node_modules/.bin/tsc --noEmit -p deliveries/si-ep10-dopamine-greenhouse/project/tsconfig.json
python3 deliveries/si-ep10-dopamine-greenhouse/project/scripts/verify_project.py
python3 skills/dual-platform-video/scripts/validate_delivery.py deliveries/si-ep10-dopamine-greenhouse --source-only

# 核验audio-authorization.json绑定当前影片文本；适用Q的默认百炼longtian_v3授权，无需逐片重复询问
python3 deliveries/si-ep10-dopamine-greenhouse/project/scripts/synthesize.py --only S01 --authorized
# 核对样本后，仅补齐其余匹配缓存
python3 deliveries/si-ep10-dopamine-greenhouse/project/scripts/synthesize.py all --authorized

# 使用含NumPy的既有Python并通过agent-dev运行
# <python> scripts/build_audio.py --mix
# 先带真实声音预览，再正式渲染
agent-dev run -- node deliveries/si-ep10-dopamine-greenhouse/project/scripts/render.mjs preview 3600 3839
agent-dev run -- node deliveries/si-ep10-dopamine-greenhouse/project/scripts/render.mjs video
```

正式交付还需要：真实PCM时长与响度、字幕时序、代表带声片段、完整5400帧视觉筛查、严格媒体解码、最终编码抽帧与播放器检查、GitHub作品Release和独立final备份核验及恢复。不能将源码检查或占位字幕当成这些步骤已完成。`review/acceptance.md`记录本次真实进度。

本次首轮Chrome捕获出现两帧顶部HUD瓦片错误。失败电影保留在本地`review/iterations/initial-90s.mp4.failed`，两张实际使用的原生重绘帧作为正式源资产保存在`public/repair-frames/`。`scripts/repair_frames.py`固定针对本次失败源散列与帧1369/4043，不能套用到其他渲染；需重放该本地诊断时，将归档PNG复制回`review/source-1369.png`与`review/source-4043.png`。失败中间电影不进入正式媒体库。一般重建应直接从可编辑源完整导出，再做全帧验收；正式成片可通过Release恢复。

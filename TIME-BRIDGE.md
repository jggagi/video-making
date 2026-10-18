# 兰亭集序 · 古今回望版

在展厅增强版上，把“后之视今，亦犹今之视昔，悲夫！”作为古今转换的视觉中心：同一曲水与竹林构图里，古人雅集隐去，空景短暂留驻，现代衣着的游客随后显现。“后之览者，亦将有感于斯文”回到这群游客，呼应正在博物馆观看影片的人。

## 成片

- `out/time-bridge/兰亭集序-古今回望版-4K.mp4`
- `out/time-bridge/兰亭集序-古今回望版-1080p.mp4`
- `out/time-bridge/古今回望-点睛片段.mp4`：包含前后转场的局部预览。
- `time-bridge-watch.html`：可直接跳到古今转换和最后一段。

完整原文、男声旁白、配乐、26 条字幕、总长 4535 帧 / 24 fps 均保持原样。原展厅增强版及更早成片继续保留。字幕文件沿用 `out/extended/兰亭集序-展厅增强版.srt` 与 VTT。

## 画面与动画

新增画作 `public/extended/modern-visitors.png`，由内置 `image_gen` 编辑生成。以既有无人曲水为底图、古人雅集为构图参考，保留山水与水墨笔触，加入穿现代夹克、衬衫、长裤、运动鞋，携背包的游客。游客是文学意象，并非兰亭现场记录或特定人物。

最终完整提示词、工具模式和原始生成文件路径保存于 `out/time-bridge/art-prompts.json`。提示词的核心要求是：只加入现代游客；固定镜位、竹林、树、岩石、水道和色调；人物不进入水中；不添加建筑、标识或文字。

古今转换镜头从全片第 3689 帧开始。镜头内第 30–64 帧古人渐隐，第 64–78 帧空景停留，第 78–114 帧现代游客渐现，后续保持现代场景。全程使用同一镜头缓移与同一水面运动遮罩，人物通过透明度转换。画面上的原文放在上部中央，避开两岸人物面部。

本次只改 `time` 与 `future` 两个镜头。此前源码备份、未改变时间轴和音轨的 SHA-256、旧成片校验值分别保存在 `out/time-bridge/source-before/` 与 `edit-contract.json`。画作原始尺寸为 1672×941，4K 视频中的背景为放大画作；字幕和水面按输出分辨率渲染。

## 重导出

```sh
npm run typecheck
LANTING_OUTPUT_DIR=out/time-bridge LANTING_EDITION=古今回望版 node scripts/render-extended.mjs time-stills
LANTING_OUTPUT_DIR=out/time-bridge LANTING_EDITION=古今回望版 node scripts/render-extended.mjs time-sample
LANTING_OUTPUT_DIR=out/time-bridge LANTING_EDITION=古今回望版 node scripts/render-extended.mjs 4k
LANTING_OUTPUT_DIR=out/time-bridge LANTING_EDITION=古今回望版 node scripts/render-extended.mjs video
LANTING_OUTPUT_DIR=out/time-bridge LANTING_EDITION=古今回望版 node scripts/validate-extended.mjs
```

本机重型渲染使用已核验开发卷的 `agent-dev run -- env … node …`，一次一个渲染任务。实际交付的 1080p 文件从 4K 成片缩小，保留相同音轨。现场大屏与音响试播仍由展厅确认。

## 本次校验

TypeScript 检查通过；4K 与 1080p 均为 4535 帧、24 fps、H.264 / AAC 48 kHz 立体声，完整解码与 fast start 检查通过。原文、旁白及字幕时序沿用；时间轴和音轨源文件的 SHA-256 保持一致。从最终 MP4 抽取的古人、空景、现代游客与结尾画面已查看；播放器两个章节按钮的实际跳转和播放已验证。详细记录在 `out/time-bridge/validation.json`。

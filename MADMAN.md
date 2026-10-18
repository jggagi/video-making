# 狂人日记 · 鲁迅

新制作的[心理悬疑改编 v5](MADMAN-V5.md)使用553字原文节选、写实生成画面与同一百炼男声，时长198.75秒，Composition `MadmanDiarySuspense`。以下保留木刻版与v1–v4的制作和验收记录。

保留的完整影片**节奏与意象加强版 v4**：79 秒 / 1920×1080 / 24 fps。保留原有 8 个章节和全部 11 段原文、143 字朗读，以及百炼“龙三叔”男声；依据已选字缝样片的力度调整全片。成片 `out/madman/狂人日记-节奏意象加强版-v4-1080p.mp4`，独立播放器 `madman-v4-watch.html`。v1、v2 和 v3 样片继续保留。

| 时间 | 段落 | v4 的画面与节奏 |
| --- | --- | --- |
| 00:00–00:05 | 题名 | 月下院墙与人影，片名渐显 |
| 00:05–00:13 | 月光 | 接续同一构图，轻微云影经过月光 |
| 00:13–00:24 | 目光 | 群像缓推，第二句转入左右面孔近景 |
| 00:24–00:44 | 字缝 | 复用认可的 20 秒样片；书页、字行聚焦、字缝开裂与“吃人”揭示 |
| 00:44–00:52 | 质问 | 暗下的人群与完整质问，背景声退去 |
| 00:52–01:03 | 自省 | 月下人影近景，“我”放大；移动阴影作为心理意象 |
| 01:03–01:12 | 孩子 | 门外光线逐渐收窄，孩子仍停在门槛内 |
| 01:12–01:19 | 呼喊 | “救救孩子……”保持到片尾，最后 3 秒寂静 |

新场景入口 `src/madman/MadmanEnhancedFilm.tsx`，时间轴 `src/madman/full-v4-timeline.json`，Composition ID `MadmanDiaryEnhanced`。书页场景复用 `MadmanHistoryScene`，在全片中取消样片末尾的淡黑，并由全片管理音轨、字幕和转场。风格变化属于对文学的艺术想象，没有新增人物行为或获救结局。

v4 音轨 `public/madman/audio/full-v4.wav`，清单 `public/madman/audio/full-v4-manifest.json`，同名 SRT/VTT 在 `out/madman/`。复用所有缓存录音，没有新云端调用，没有改变语速或音高；按段调整音量和背景风声。24–44 秒的字缝声音为样片 PCM 逐字节复用，最后 76–79 秒为真实静音。12 条字幕拼接后与原 11 段原文完全一致。

重制 `npm run madman:v4:prepare`；渲染 `npm run madman:v4:stills` / `npm run madman:v4:sample` / `npm run madman:v4:render`；验证 `npm run madman:v4:validate`。本机仍以 `agent-dev run --` 包装渲染，一次只进行一项渲染，并发 1。最终证据 `out/madman/validation-full-v4.json`：1896 帧、79 秒 H.264/AAC，BT.709 有限范围、yuv420p、fast start；完整解码通过，AAC 峰值约 -4.47 dBFS。已查看 13 张最终抽帧、实际播放 4 秒转场样片、连续播放完整版至 79.019 秒结束，并验证全部 8 个章节跳转。主播放器已停在片头。人工听感和现场大屏评价由实际听看确认。

新增**20 秒字缝加强样片 v3**，用于与完整男声配音版 v2 比较。样片保留第三节原有三句节选，重新安排句间停顿；在第三句原有静音处插入 0.45 秒停顿，所有发音采样保留。书页逐步逼近，字行“仁义道德”聚焦，页面从字缝分开后显露暗红“吃人”。字幕在该句内分为两次呈现，拼接后与原选中字句完全一致。

样片复用百炼龙三叔缓存录音，没有新云端调用；纸页与室内风声由固定种子的本地程序生成，12.75–14 秒保留真实静音。新混音分层为 `public/madman/audio/history-study-v3{-voice,-paper}.wav`；可检查清单为 `public/madman/audio/history-study-v3-manifest.json`。场景入口 `src/madman/MadmanHistoryStudy.tsx`、时间轴 `src/madman/history-study-v3.json`，Composition ID `MadmanHistoryStudy`。

交付 `out/madman/狂人日记-字缝加强样片-v3-1080p.mp4`，同名 SRT/VTT；对比页 `madman-history-watch.html` 可重放样片或原版 29–48.33 秒章节，两段视频交替播放。重制用 `npm run madman:history:prepare`，渲染用 `npm run madman:history:stills` / `npm run madman:history:render`，校验用 `npm run madman:history:validate`。渲染按下面的本机存储和并发规则运行。

样片为 1920×1080、24 fps、480 帧/20 秒（容器 20.011 秒），H.264/AAC、BT.709 有限范围、yuv420p、fast start；完整解码通过，AAC 峰值约 -4.47 dBFS。记录 `out/madman/validation-history-v3.json`。该样片现已作为 v4 字缝段的依据，独立样片继续保留；完整人工听音评价仍由实际试听确认。

保留的**男声配音版 v2**：1920 × 1080 / 24 fps / 91.33 秒。使用百炼 CosyVoice v3 Flash 的“龙三叔”预置男声（`longsanshu_v3`），0.92 倍语速，朗读原有 11 段、143 字原文节选；未加入额外解说。成片路径 `out/madman/狂人日记-男声配音版-v2-1080p.mp4`，独立播放器 `madman-voice-watch.html`，可编辑入口 `src/madman/MadmanVoicedFilm.tsx`，Composition ID `MadmanDiaryVoiced`。

配音按段缓存于 `public/madman/voice-v2/`，清单核对返回模型、音色、原文、实际时长及文件散列。字幕与镜头从真实音频采样数排布；“仁义道德”句所在镜头延长 32 帧（1.33 秒），后续章节顺延。“吃人”字缝揭示跟随第三句朗读。48 kHz 双声道混音在人声期间压低原有氛围声；不是鲁迅本人录音或声音克隆。

新时间轴 `src/madman/voiced-timeline.json`，新音轨 `public/madman/audio/voiced-v2.wav`，混音与覆盖范围清单 `public/madman/audio/voiced-v2-manifest.json`，新 SRT/VTT 在 `out/madman/`。云端只发送这 143 字公开原文及其生成音频用于自动转写核对，没有发送工程私密文件。自动转写中的“每页/每叶”“对吗/对么”“4000/四千”按已记录规则归一化后，选中字句完整匹配；可见字幕仍保留原文写法。记录 `out/madman/voice-v2-spoken-check.json`，不将自动转写视为人工听音。

使用现有项目本地百炼 CLI 2.1.0，与技能和当日 npm 发布版本一致。音色能力依据[百炼官方音色表](https://help.aliyun.com/en/model-studio/cosyvoice-voice-list)。通过 `node scripts/synthesize-madman-voice.mjs plan` 可查看不调用服务的计划；`sample` 验证第一句，`all` 复用匹配缓存并补齐全部配音。重制混音用 `node scripts/prepare-madman-voice.mjs`；渲染与验证用 `scripts/render-madman-voice.mjs`、`scripts/validate-madman-voice.mjs`。

配音版已通过 TypeScript、完整音视频解码、最终抽帧和全部 11 段朗读的字幕/镜头覆盖检查。最终 H.264 / AAC 为 2192 帧、91.33 秒，BT.709、yuv420p，48 kHz 双声道音轨峰值约 -4.19 dBFS，无削波，支持 fast start。已实际播放 11 秒配音样片，并验证新版播放器的播放与章节跳转。详细证据在 `out/madman/validation-voice-v2.json`；未进行完整人工听音或现场大屏试播。

以下记录保留的无旁白 v1，播放器 `madman-watch-v1.html`。

90 秒 / 1920 × 1080 / 24 fps，原文节选、黑白木刻与暗红字缝、原文字幕加本地生成的氛围声音。没有旁白。影片以狂人的日记视角组织意象；没有将他的怀疑当成现实事件的复原。

成片：`out/madman/狂人日记-木刻意象版-v1-1080p.mp4`。播放器：`madman-watch-v1.html`。可编辑入口：`src/madman/MadmanFilm.tsx`，Composition ID：`MadmanDiary`；精确时间轴：`src/madman/timeline.json`。

## 文本与原始画面版分镜

依据[维基文库《狂人日记》简体通行版](https://zh.wikisource.org/zh-hans/狂人日記)，核对日期 2026-10-11。采用“很好的月光”，没有混用 1918 年初刊本的“狠好的月光”。原著作者鲁迅，作品署期一九一八年四月。原文是公有领域作品。

字幕为按原作章节顺序选择的独立节选，省略其间叙述。引号统一为现代中文双引号；其余选中字句保留，未将新写解说当作鲁迅原文。第三节在“仁义道德”句和“满本”句之间省去失眠与细读半夜的叙述；末尾仍保留“或者还有？”和省略号，不补写孩子已经获救。

| 时间 | 原文位置 | 画面与动作 |
| --- | --- | --- |
| 00:00–00:06 | 题名 | 月下院墙与人影，片名渐显 |
| 00:06–00:17 | 一 | 月光、孤身人影，镜头缓慢靠近 |
| 00:17–00:29 | 二 | 群像从两侧逼近，表现被注视的感觉 |
| 00:29–00:47 | 三 | 可控排版的书页，“仁义道德”间展开字缝，露出“吃人” |
| 00:47–00:59 | 八 | 群像压暗，“从来如此，便对么？”分两次显现 |
| 00:59–01:12 | 十二 | 暗色人影与栅线，“我也在其中”进入画面 |
| 01:12–01:23 | 十三 | 孩子停在门槛内侧，保持原文的疑问 |
| 01:23–01:30 | 十三 | “救救孩子……”稳定停留，最后保留完成的片尾 |

## 素材与声音

三幅插画由内置 image_gen 生成，原始尺寸均为 **1672 × 941**，导出时放大与少量裁切为 1920 × 1080。属于基于文学的艺术想象，不是史料、历史照片或实际木刻版画。完整提示词及风格参考关系在 `public/madman/art-prompts.json`；选中图片在同目录。

书页、字缝、人影、栅线、尘点和文字是可编辑的 React/SVG 图形；运动全部由帧数驱动。字体使用本机 Songti SC、PingFang SC，不包含鲁迅手稿或仿造真迹。

`public/madman/audio/atmosphere.wav` 为固定种子的本地程序声音：风噪、低音、转场轻敲和片尾少量泛音；无现成音乐录音、真人配音或云端 TTS。48 kHz、双声道、16 位 PCM、90 秒；清单在同目录 `manifest.json`。独立 SRT/VTT 在 `out/madman/`，已烧录或作为主体呈现的原文可以不开启播放器附加字幕。

## 重导出

沿用工程已有 Remotion 4.0.534 与锁文件，不需要重装或升级。

```sh
node scripts/prepare-madman.mjs
npm run typecheck
node scripts/render-madman.mjs stills
node scripts/render-madman.mjs sample
node scripts/render-madman.mjs video
node scripts/validate-madman.mjs
```

在 Q 的本机，渲染前核验最新 `agent-dev status --json`，以 `agent-dev run -- node scripts/render-madman.mjs …` 运行，一次只做一项渲染、浏览器渲染并发 1。可通过 `REMOTION_BROWSER_EXECUTABLE` 指定 Chrome。

播放器可使用既有 `node scripts/serve-preview.mjs`，访问 `http://127.0.0.1:8031/madman-watch.html`。最终探测、解码、画面与播放器验证结果记录在 `out/madman/validation.json`；只以实际记录为准。

## 原始画面版验收

TypeScript 与三个脚本语法检查通过。8 个镜头时间轴连续，11 段原文字幕按顺序、不重叠、位于镜头范围内，并检查了阅读时间。已查看 11 张代表静帧、六秒转场样片的真实播放及转场中点、最终视频的 11 个抽帧。

最终成片为 H.264 High / AAC，1920 × 1080，24 fps、2160 帧，BT.709、有限色彩范围、yuv420p，MP4 fast start。画面时长 90 秒；容器与 AAC 时长约 90.005 秒，包含编码尾部。音视频完整解码无错误；最终 AAC 峰值约 -14.8 dBFS，无削波。

本地播放器实测了播放、字缝/质问/呼喊章节跳转、片尾播放结束；独立 VTT 下载路径返回 HTTP 200。播放器预览保存在 `out/madman/player-preview.png`。未进行完整人工听音或现场大屏试播。

# 兰亭集序 · 展厅增强版

本版使用 Remotion 4.0.534，横向 16:9、24 fps，共 4535 帧，时长 188.958 秒。完整保留《兰亭集序》17 段原文及原文顺序，提供 26 条同步字幕。第一版与博物馆第二版均保留。

## 播放文件

- `out/extended/兰亭集序-展厅增强版-4K.mp4`：3840×2160，H.264 / AAC 立体声，用于展厅播放。
- `out/extended/兰亭集序-展厅增强版-1080p.mp4`：1920×1080，便于预览与传输。
- `extended-watch.html`：离线播放器，支持全屏与循环。
- 同目录 SRT / VTT 原文字幕、男声旁白 WAV，以及制作与校验记录。

## 本版变化

新增六张水墨画面：竹林仰视、两位文人室内交谈、溪边草木细景、文人近景、展卷特写、晴朗天空。加上既有溪流、雅集、空溪、山水、书房、纸面，形成更丰富的镜头变化。配色仍为暮春的淡青、石绿与纸色；人物场景是文学意象演绎，不对应可证的个人肖像或历史现场复原。

“群贤、少长”表现雅集；“茂林修竹”切向竹林；“仰观、俯察”分别表现开阔天空和溪边生物；“悟言一室”表现两位文人交谈。对“已为陈迹”的空溪淡化是记忆意象。保留对“一死生”“齐彭殇”的明确否定，不把此文处理为纯粹欢乐的雅集宣传片。

水面采用限定在溪流中的像素位移与动态高光，杯子沿水道移动，并有倒影、扩散水纹与尾迹。前景竹叶局部分层摆动、蝴蝶轻扑、室内光影漂移与镜头缓慢移动均由帧数驱动，支持准确跳转。书写沿真实现代字形轮廓逐笔显现；它是现代字形动画，不能标作王羲之真迹或《兰亭序》临摹原件。卷面“死生亦大矣”也是后期排字的文学示意。

画作原始尺寸约为 1672×941，在 4K 成片中放大；字幕、字形轮廓与水面渲染按目标分辨率输出。4K 文件的输出分辨率不等于背景画作原生 4K。

## 配音与来源

使用阿里云百炼中国站 `cosyvoice-v3-flash` / `longsanshu_v3`（龙三叔，沉稳质感男）。这是合成男声。没有克隆具体人物，也没有声称是真人录音。全文采用 24 kHz 单声道 WAV 源音频，再与本地合成的稀疏弦音、水声、风声混成双声道。已授权的 TTS 输入只包含公开原文与语速、读音控制，未发送私人材料。

按 [百炼官方价格页](https://help.aliyun.com/zh/model-studio/model-pricing) 2026-10-11 查询，北京 `cosyvoice-v3-flash` 输入价格为每万字符 1 元。实际账单、免费额度与试音计费以账户为准。[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list) 与 [SSML 文档](https://help.aliyun.com/zh/model-studio/ssml-latex-user-guide) 为音色和发音控制依据。没有使用支持范围之外的自然语言音色指令。

`out/extended/manifest.json` 保存实际模型、音色、语速、原文、音频散列与时长；`out/extended/art-prompts.json` 保存素材生成提示及本地来源。音频以内容散列缓存，已有音频校验通过后复用。清单不保存 API Key、登录令牌或带签名的下载 URL。百炼 CLI 2.1.0 安装在项目 `out/tools/bailian-cli`，未变更全局 Node 工具链。

## 复现

```sh
node scripts/synthesize-extended.mjs --plan
# 下行会调用已配置的百炼账户，可能计费；已有有效音频会复用。
node scripts/synthesize-extended.mjs
node scripts/prepare-extended.mjs
npm run typecheck
/Users/guoq/.local/bin/agent-dev run -- node scripts/render-extended.mjs stills
/Users/guoq/.local/bin/agent-dev run -- node scripts/render-extended.mjs 4k
```

4K 渲染使用一个渲染线程；1080p 交付由 4K 成片缩小生成。`scripts/validate-extended.mjs` 核对原文、时间线、帧数、规格、快速起播、整段视频解码和散列，并从最终 MP4 抽取代表画面。验证结果位于 `out/extended/validation.json`。

现场大屏的观看距离、亮度与外放音量仍需在兰亭博物馆试播调整。可先用 1080p 预览，正式播放使用 4K 文件；循环点保留短暂纸色停顿。

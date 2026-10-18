# 兰亭集序 · 博物馆版

为横向展厅大屏和外放声音制作的 Remotion 第二版。16:9，24 fps，3989 帧，约 2 分 46 秒。第一版及其成片保留。

## 展示文件

- `out/museum/兰亭集序-博物馆版-4K.mp4`：3840 × 2160 展厅播放文件，H.264 / AAC，立体声 48 kHz。
- `out/museum/兰亭集序-博物馆版-1080p.mp4`：便于审看和普通屏幕播放的文件。
- `out/museum/兰亭集序-博物馆版.srt`、`.vtt`：26 段全文字幕。
- `museum-watch.html`：本地播放器，支持全屏和循环。

背景画的原始尺寸约为 1672 × 941，4K 导出时放大；汉字、字幕、水面效果按 4K 渲染。4K 文件不代表全部素材都是原生 4K。

## 画面处理

片头以准确汉字笔顺逐笔写出“蘭亭集序”；“一觴一詠”和“錄其所述”呼应正文。清流的纹理局部流动，独立耳杯随曲水漂行并带有水波。竹枝作为前景图层摆动，远山保持稳定，营造层次。

全文 324 字保持原文顺序、逐句朗读和字幕对应。春日雅集沿曲水列坐，不添加现场乐队。原文进入“情随事迁”“已为陈迹”时，同一雅集画面叠化为空景，作为回忆与时间的意象；不叙述虚构的人物死亡。“固知一死生为虚诞，齐彭殇为妄作”完整显示，保持否定判断。

正文字幕位于画面下方安全区域，1080p 逻辑字号 42 px（4K 为 84 px），用淡米色字与深色渐变保证可读性。最终视距、设备 overscan、展厅亮度和音量需以现场试播为准。

## 素材与书法边界

画面和器物为 AI 辅助的艺术意象，不是历史照片、现场录影或考证复原。片中书写使用 Arphic 字形轮廓和汉字笔顺数据，属于现代排字的书写可视化，不是王羲之书迹，也不是摹本动画。馆内展签可以说明：“画面为依据《兰亭集序》创作的意象动画；书写为现代字形演示。”

笔顺数据来自 [Hanzi Writer Data](https://github.com/chanind/hanzi-writer-data)，衍生自 Make Me a Hanzi 与 Arphic 字体；完整 [Arphic Public License](public/museum/strokes/ARPHICPL.TXT) 随工程保留，数据未修改。画面提示词在 `public/museum/art-prompts.json`。背景与独立图层在 `public/museum/`。

文字依据[维基文库《兰亭集序》](https://zh.wikisource.org/wiki/%E8%98%AD%E4%BA%AD%E9%9B%86%E5%BA%8F)通行原文核对。馆藏书法的背景阅读参考[故宫博物院“冯承素行书摹兰亭序卷”](https://www.dpm.org.cn/collection/handwriting/228279.html)；影片没有使用该藏品图像。展示主题参考[兰亭书法博物馆介绍](https://www.sxlanting.com/museum/)。

## 声音

现版使用本机 macOS Tingting 合成朗读，多音字发音校准继承第一版；可见原文不改。配乐为本地程序生成的稀疏弦音，加入轻微水声、风声与立体声空间，后半段音色降低。音轨峰值约 -3.2 dBFS，无削波。声音不宣称为现场录音或古琴演奏录音。

用于正式展陈前，建议更换为经过馆方审定的真人朗读，并在实际展厅核对发音、视距、音量与循环衔接。本次交付是可播放、可审看的完整创作版本，尚未经过馆方学术审定或现场验收。

## 编辑和重导出

```sh
npm run typecheck
npm run museum:prepare
npm run museum:stills
npm run museum:4k
npm start
```

Remotion Studio 中选择 `LantingMuseum` 或 `LantingMuseum4K`。第二版源码在 `src/museum/`；第一版 composition 为 `Lanting`。准备脚本读取第一版时间轴和已验证的本地语音源，在片头增加 10 秒、片尾增加 4 秒，不改变正文 cue 的相对时间。可以直接使用保存的音轨，不必重跑准备脚本。

Mac 工作站上通过 `agent-dev run -- …` 执行大渲染，4K 渲染并发为 1。重导出需要本机 Chrome，其他路径可用 `REMOTION_BROWSER_EXECUTABLE` 设置。

```sh
/opt/homebrew/bin/ffmpeg -i out/museum/兰亭集序-博物馆版-4K.mp4 -vf scale=1920:1080 -c:v libx264 -crf 18 -preset medium -c:a copy -movflags +faststart out/museum/兰亭集序-博物馆版-1080p.mp4
```

验证记录与代表画面保存在 `out/museum/`。完整解码和媒体参数检查结果记录在 `validation.json`。

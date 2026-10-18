# UHD v3 交付说明

## 画布与渲染

- 成片规格：3840×2160、60 fps、10,800 帧、180 秒。
- 视觉组件继续使用 1920×1080 逻辑坐标。根合成将整个 SVG / DOM 场景统一缩放 2 倍，并直接渲染至 3840×2160 的 Remotion composition；视频没有经过 1080p 成片放大。
- 因此，逻辑画布中的字体字号、SVG 描边、间距、边距和布局在最终 4K 画面上都呈 2 倍尺寸，矢量内容按原生合成尺寸栅格化。
- 青色与金色重点物件采用成组的柔光滤镜：逻辑坐标下约 20 px 的外层光晕在成片上约为 40 px，并叠加较紧凑的高亮边缘。按组应用滤镜，避免对每个粒子单独创建滤镜。

## 语言

旁白、主标题、叙事字幕和核心概念使用简体中文。英语仅保留在技术遥测、状态码、矩阵尺寸、数学标签及明确的界面技术标题，例如 `BIOLOGICAL WORKING MEMORY`、`ACTIVE CONTEXT MANIFOLD`、`ORACLE OUTPUT >>`。中文字幕由 `npm run captions` 导出至 `out/cage-of-seven-plus-two-uhd-v3-zh.srt`。

## 音轨连续性与隐私边界

本版继续使用本地缓存的 17 段百炼旁白与既有混音，不重新调用语音生成服务、不改变配音源文件。原有声音设计、采样边界和四幕时间点由 `timeline.json` 保持。旁白核对限定为本地检查；用户明确选择不上传音频进行 ASR，因此本版没有安排 ASR 上传。

## 本地命令与产物

```sh
npm run stills
npm run preview:overload
npm run preview:manifold
npm run render:4k
npm run render:score
npm run captions
npm run validate:4k
python3 scripts/package.py --uhd
```

主旁白版目标路径为 `out/cage-of-seven-plus-two-uhd-v3-4k.mp4`。配乐版目标路径为 `out/cage-of-seven-plus-two-score-v3-4k.mp4`。可复用源工程归档为 `out/cage-of-seven-plus-two-uhd-v3-project.zip`；打包脚本会在归档内附带文件哈希，并写入独立的 `out/uhd-v3-package-manifest.json`。完整 MP4 与临时 Remotion bundle 不装入源工程 ZIP。

`out/uhd-v3-validation.json` 记录自动尺寸、帧率、时长、音轨与解码检查的实际结果。自动检查能证明文件参数和可解码性，不能代替人工完整观看、听音或目标显示器验收；这些状态应以最终 QA 记录为准。

## 历史归档

历史 1080p 成片、v1 / v2 源工程 ZIP 与它们的打包收据均保留。4K 打包使用单独的 `--uhd` 模式、输出文件名和收据，不覆盖历史 ZIP。

## 本次交付验收

已导出中文旁白成片 `out/cage-of-seven-plus-two-uhd-v3-4k.mp4`。实际视频为 3840×2160、恒定 60 fps、10,800 帧、180.000 秒；AAC 与容器的呈现时长为 180.011 秒，11 ms 尾部填充单独记录。配乐版保留导出命令，本次交付的是中文旁白版。

类型检查、确定性与时间轴检查、4K 过载短片完整解码、整片音视频严格解码均通过。从实际 MP4 提取的 13 个代表帧和原生关键帧已经模型目视检查；结果见 `out/uhd-v3-final-contact-sheet.png` 与 `out/uhd-v3-source-review.json`。

58 个音频及缓存文件通过哈希核对。成片 AAC 解码后与缓存混音按同一时刻比较，整片相关系数为 0.99993，四幕分别大于 0.99984；该检查允许 AAC 有损编码误差，不代表逐字发音或听感验收。全部检查在本地完成，没有 ASR 上传。

完整人工观看、连续听音及目标 4K 显示器播放仍待用户验收。自动检查的细项、哈希和音轨比较结果保存在 `out/uhd-v3-validation.json`。

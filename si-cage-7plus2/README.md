# 7±2 的囚笼 · 第二期

可编辑的 React / Remotion 程序化短片工程。当前制作目标为 **3840×2160、60 fps、10,800 帧、180 秒**。画面以 1920×1080 的逻辑 SVG / DOM 舞台绘制，再整体以 2 倍比例在 4K 合成帧中栅格化；输出尺寸来自原生 4K 渲染，不是把已编码的 1080p 成片放大。字体、描边、留白和布局均随画布等比扩大。青色与金色重点元素使用分组柔光。

旁白、主标题与核心叙事以专业简体中文呈现。英语只用于技术遥测、状态码、矩阵尺寸、数学标记及界面技术标题，例如 `BIOLOGICAL WORKING MEMORY`、`ACTIVE CONTEXT MANIFOLD` 和 `ORACLE OUTPUT >>`。

## 运行与导出

```sh
npm ci
npm run typecheck
npm run check
npm start
```

```sh
npm run stills          # 原生 4K 代表帧
npm run preview:overload
npm run preview:manifold
npm run captions        # 导出简体中文字幕
npm run render          # 完整 4K 中文旁白版
npm run render:4k       # 同上
npm run render:voiced   # 同上
npm run render:score    # 完整 4K 配乐版
npm run validate:4k     # UHD 成片与音频验证
```

完整中文旁白版目标文件为 `out/cage-of-seven-plus-two-uhd-v3-4k.mp4`；配乐版为 `out/cage-of-seven-plus-two-score-v3-4k.mp4`。`npm run render:legacy:voiced` 保留旧 1080p 混流辅助脚本，仅用于兼容旧素材。具体渲染和验证结果以 `out/uhd-v3-validation.json` 及 [UHD-V3.md](UHD-V3.md) 的更新记录为准。

在 Q 的工作站上执行依赖安装或渲染前，先按工作站说明检查外置卷，并通过 `agent-dev run -- ...` 执行较重任务。`REMOTION_BROWSER_EXECUTABLE` 可指定已安装的 Chrome；`REMOTION_CONCURRENCY` 默认值为 2。Studio 使用端口 3107。

## 声音与旁白

`generate-audio-ep2.js` 从 `timeline.json` 读取事件时间，在 48 kHz 下合成 60 fps 声画同步的本地 PCM。九颗琥珀色球体在第 0 至 960 帧逐颗增加正弦泛音；第 1200 帧触发失真噪声，第 1212 帧硬切静音。第 6700 帧的高维流形出现时，切换为原创的巴赫赋格风格四声部模仿对位；这不是巴赫具体作品的录音或复刻。

当前 4K 中文旁白版复用此前通过百炼生成并缓存在本地的 17 段配音和混音。此次分辨率与画面文字调整没有重新生成、上传或改动配音素材。用户选择了仅在本地检查；本项目不执行旁白 ASR 上传。旁白来源、缓存清单、混音参数及既有测量结果见 [VOICED-V2.md](VOICED-V2.md)。

## 四幕结构与时间点

| 幕 | 全局帧区间（结束帧不含） | 内容 |
| --- | ---: | --- |
| 一 | 0–2700 | 琥珀色工作记忆网络、第十变量触发与片名 |
| 二 | 2700–5400 | 线性拟合、离群点与 40×40 注意力矩阵 |
| 三 | 5400–8400 | 推理隧道与 120 顶点、240 条边的 4D 环面结 |
| 四 | 8400–10800 | 金色投影、人类认知平面、结尾与第三期钩子 |

计时点沿用既有设计：噪声 1200、矩阵 3800、流形 6700、神谕投影 8400、结尾 10000、下期钩子 10550。叙事中的能力数字属于概念性视觉表达，并非实测科学基准；流形是确定性的 4D 环面结投影。

## 工程与交付

`src/`、`scripts/`、`timeline.json`、`generate-audio-ep2.js` 和本地音频素材组成可编辑工程。`npm run check` 检查时间轴、代码约束和 PCM 静音边界；`npm run validate:4k` 用于验证 4K 输出和音轨。自动解码及代表帧检查不能代替完整观看、耳机试听或目标屏幕验收。

使用 `python3 scripts/package.py --uhd` 生成**新的** `out/cage-of-seven-plus-two-uhd-v3-project.zip`。归档包含源码、脚本、时间轴、文档、原始配乐、缓存旁白及紧凑 QA 文件，带逐文件 SHA-256 清单；完整成片另行交付。既有 v1 / v2 压缩包和收据作为历史记录保留，不会被 4K 打包流程覆盖。

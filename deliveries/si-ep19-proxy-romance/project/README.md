# EP19 · 替身社交

90.00秒、60fps、5400帧，原生2160×3840，纯二维SVG剧场。完整用户brief在 `../source/script.md`；实测时长约束下获准的精简配音在 `adapted-script.md`，原始三轨文本在 `segments-original.json`。

从作品目录打开 `../watch.html`。本地HTTP预览可在作品目录运行 `python3 -m http.server --bind 127.0.0.1 8199`，再访问浏览器。完整影片与样片分开选择。

依赖锁定Remotion4.0.534、React19.1.0、TypeScript5.9.3。优先复用仓库工具链；独立恢复时用本目录锁文件 `npm ci`，不要升级版本。Mac上所有渲染/重建遵守仓库的 `agent-dev` 卷身份与容量预检，渲染器还限制180帧批次以控制可重建PNG临时空间。没有现成工具链时按当前机器约定安装，不创建内部回退环境。

```sh
npm run typecheck
node scripts/verify_project.mjs
node scripts/render.mjs stills 60 2100 2940 3900 4860 5040 5399
node scripts/render.mjs preview 4800 4979
node scripts/render.mjs video
python3 scripts/mux.py
python3 scripts/verify_encoded_audio.py
```

正式渲染和混音拒绝覆盖成片或已有母带；新改版须新版本目录或显式保留旧产物后继续，不能盲重跑。`render.mjs video` 输出独立视频轨到受控scratch，通过 `mux.py` 与已核验PCM组合。1080逻辑坐标直接在2160宽度栅格化，没有把1080p视频上采样。

旁白已经缓存，普通重建不需要云调用。`synthesize.py` 只在已授权范围内生成缺失缓存，模型/声音或文本哈希不符即停止。`build_audio.py --mix` 构造原生48kHz双声道母带与三个分轨；已有母带不覆盖。随后运行 `make_captions.py` 应用本片的语意分句。字幕时间是实测语音活动区间内的字符权重估计，并非逐字强制对齐。

音乐、玻璃、水面、丝线和拨弦音效全部为本地代码生成，未使用外部音乐；不是声学乐器实录。静音严格为帧[4860,4890)，样本[3888000,3912000)。AAC编码可出现边界泄漏，必须与母带的精确零区分记录。

字体使用合法安装的macOS系统PingFang SC、Songti SC、Menlo/SFMono。字体不随项目再分发；相同字体环境有助于一致重建，其他系统需先检查替代字体与缺字，不能把不同字体渲染当成逐像素复现。

画面、素材、时间轴和当前音轨散列见 `assets-manifest.json`；最终媒体与逐帧扫描的绑定见 `../review/`。技术报告不代表人工完整观看、发音、听音、手机App或普通观众体验已通过。

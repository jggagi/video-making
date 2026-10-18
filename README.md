<!-- video-making archive overview -->
# video-making

从剧本到双平台短片的制作技能、可编辑工程与作品档案。

- [剧本双平台短片 Skill](skills/dual-platform-video/SKILL.md)：新作默认两版均为 **120 秒、原生 4K**，B站 **3840×2160 横屏**，小红书 **2160×3840 竖屏**；共用素材、配音与时间轴，分别设计排版，减少重复生成消耗。
- [全部成片与工程下载](https://github.com/jggagi/video-making/releases)：每部作品独立 Release，包含完整成片、历史版本、样片与工程 ZIP。
- [全部作品索引](deliveries/README.md)：包含历史作品与之后的新作，每次归档自动更新。
- [机器可读媒体目录](archive/catalog.json)：51 个既有资产，共 5,173,284,551 字节，逐文件 SHA-256 与实测规格。
- [本次历史归档的远端核对记录](archive/verification.json)：全部 51 个资产均已公开，远端大小、SHA-256 和下载地址与清单一致，并抽测了公开视频的下载恢复。

Git 保存技能、源码、锁文件、本地音频/美术素材、字幕和精简验收记录；较大的视频和 ZIP 放在同一仓库的 Releases。视频仍保留原工程相对路径，可用清单恢复。历史作品保留原时长与画幅，不补做不存在的版本，也不声称满足后续两分钟约定。

## 本次归档的历史作品

| 作品 | 完整成片 | 样片/草稿 | 工程 ZIP |
| --- | ---: | ---: | ---: |
| [兰亭集序](deliveries/legacy-lanting/README.md) | 7 | 3 | 0 |
| [狂人日记](deliveries/legacy-madman/README.md) | 4 | 6 | 0 |
| [一眼万年](deliveries/legacy-si-eternity/README.md) | 4 | 5 | 4 |
| [7±2 的囚笼](deliveries/legacy-si-cage-7plus2/README.md) | 5 | 5 | 5 |
| [余问 QStory EP.03：十万亿个分身](deliveries/legacy-qstory-ep03/README.md) | 1 | 1 | 1 |

作品目录内的 `B站/`、`小红书/` 索引按画幅分类，不表示已发布到平台账号。人工完整观看、听音和设备验收仍以各作品实际记录为准。

## 使用与复现

在 Codex 中调用 `$dual-platform-video` 并提供剧本。技能源文件位于 `skills/dual-platform-video/`，可在本机技能目录安装后调用；现有工程分别使用自己的 README 与锁文件。

克隆仓库后，需要成片或历史工程 ZIP 时先预览下载集合：

```sh
python3 scripts/fetch-archive-assets.py --work si-eternity
python3 scripts/fetch-archive-assets.py --work si-eternity --download
```

省略 `--work` 会选中全部作品。下载器验证大小与 SHA-256，并恢复到原始相对路径；已存在且匹配的文件跳过，不覆盖不同内容。

## 后续作品同步

新作品保存在 `deliveries/<作品版本>/`，其中 `B站/` 和 `小红书/` 分别放两版成片，`source/`、`project/`、`review/` 留存剧本、工程和验收证据。完成技术检查后，更新清单、按路径提交并 push 源码与索引，再上传该版本的 Release：

```sh
python3 scripts/build-archive-catalog.py
python3 skills/dual-platform-video/scripts/upload_releases.py --catalog archive/catalog.json --root .
# 确认源码提交已 push 后，再执行：
python3 skills/dual-platform-video/scripts/upload_releases.py --catalog archive/catalog.json --root . --apply --target <完整commit-SHA>
```

上传会先创建 draft，逐项核对远端大小及 SHA-256 后再公开 Release。中断可续传；不会覆盖同名而内容不同的旧文件。具体授权和完成条件见 [GitHub 归档约定](skills/dual-platform-video/references/github-archive.md) 与 [AGENTS.md](AGENTS.md)。

---

以下保留最早的《兰亭集序》工程说明，供历史复现。

# 兰亭集序 · 水墨短片

同一工程新增[《狂人日记》心理悬疑改编 v5](MADMAN-V5.md)：553字原文节选、3分19秒、1080p；写实生成画面与百炼男声，保留“真疯了还是被逼疯”的双重解释。观看入口 `madman-watch.html`，独立入口 `madman-v5-watch.html`；[木刻版与v1–v4记录](MADMAN.md)保留。

最新为[古今回望版](TIME-BRIDGE.md)：在“后之视今，亦犹今之视昔”处，让同一曲水边的古人渐隐、现代游客出现，结尾“后之览者”再作呼应。约 3 分 9 秒，4K / 1080p；打开 `time-bridge-watch.html` 播放。

此前[展厅增强版](EXTENDED.md)新增六张水墨场景、独立风竹与蝴蝶运动，并使用百炼 CosyVoice v3 Flash 沉稳男声阅读全文；打开 `extended-watch.html` 播放。以下版本仍保留。

已新增面向横向展厅大屏的[博物馆版](MUSEUM.md)，包含水波、杯行、风竹与逐笔书写动画。打开 `museum-watch.html` 观看第二版；以下为保留的第一版说明。

用 Remotion 制作的 16:9 原文短片，1920 × 1080，24 fps，时长约 2 分 32 秒。全文 324 字按原文顺序朗读，配 17 个正文镜头、片头、片尾与逐句字幕。

成片在 `out/兰亭集序.mp4`；独立字幕在 `out/兰亭集序.srt`。打开 `watch.html` 可在本地观看。

## 画面与文本

文本以[维基文库《兰亭集序》](https://zh.wikisource.org/wiki/%E8%98%AD%E4%BA%AD%E9%9B%86%E5%BA%8F)原文核对，采用现代简体通行写法，包括“修禊”“快然”“悟言”“趣舍”。古文属于公有领域。

- 兰亭雅集：暮春、山林修竹、清流、沿曲水列坐的文士、浮动的耳杯；不出现乐队或盛大的宴席。
- 俯仰一世：从欣于所遇转向情随事迁、旧日陈迹与生命有限，以相同春景的色调变化与流水承接。
- 后之览者：临文阅读、记录与后世的感怀；完整保留“一死生为虚诞，齐彭殇为妄作”的否定。

四张水墨画面由内置 `image_gen` 制作，是依据文本的艺术想象，不是历史照片、复原考证或王羲之书法真迹。最终提示词保存在 `art-prompts.json`，素材保存在 `public/images/`。

朗读使用本机 macOS Tingting 中文合成语音，若干多音字用同音字校准，仅影响送入语音引擎的文本，不改变可见字幕。完整列表在 `scripts/text.mjs`；音轨包含本地程序生成的稀疏五声音阶弦音与轻微溪流氛围，不是现场录音。可将 `public/audio/soundtrack.wav` 换为真人朗读后重新校准时间轴。

## 预览与导出

```sh
npm ci
npm start
```

Remotion Studio：`http://localhost:3100`，composition ID 为 `Lanting`。

```sh
npm run typecheck
npm run audio
npm run stills
npm run render
node scripts/export-captions.mjs
```

音频生成脚本依赖 macOS `say` 与 `/opt/homebrew/bin/ffmpeg`。现成的音轨和时间轴已随工程保存，重导出不必重新生成音频。渲染脚本默认使用本机 Chrome；其他机器可设置 `REMOTION_BROWSER_EXECUTABLE` 指向 Chrome。字体优先使用 macOS 的 Songti SC。

Q 的 Mac 工作站安装、音频、渲染使用已核验卷身份的 `agent-dev run -- …`。同时仅一项大渲染，渲染并发为 2；内置盘空间提示仅作警示。未迁移源代码或更改其他服务。

Remotion API 参考：[renderMedia](https://www.remotion.dev/docs/renderer/render-media)。依赖版本由 `package-lock.json` 锁定。

## 已验证

TypeScript 检查通过；26 个字幕段完整覆盖原文、时间轴连续；10 张代表画面及最终 MP4 抽帧检查通过。最终文件为 H.264 / AAC、1920 × 1080、24 fps、3653 帧，已完整解码无错误。音轨峰值约 -3.2 dB，没有削波；MP4 已启用 fast start。检查记录在 `out/validation.json`。朗读为合成语音，未做真人配音或人工听音验收。

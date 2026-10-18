# EP04 v3 · 直观结尾版

保留v2前105秒、原剧本、十段旁白、19段字幕和完整声音母带，简化最后15秒。旧版均保留。v2前段中的版号属于原画面；v3新尾段显示v3。理论依据见theory-and-visual-model.md，变更动机见brief.md。

依赖锁定Remotion4.0.534/React19.1.0/TypeScript5.9.3。现有仓库工具链可直接使用。macOS渲染使用系统Chrome和本地中文字体；独立重建需合法安装中文字体并核对布局。

完整独立重建：从project目录运行 npm run typecheck，然后遵循工作站README及卷检查，串行执行 agent-dev run -- node scripts/render.mjs video landscape 和 portrait。再执行 python3 scripts/sync_audio.py --prepare 及 --apply，让两版共用同一AAC流。无需任何云端调用。

本次省时路径：先串行执行 render.mjs tail landscape / portrait，生成6300..7199帧原生4K无声片段；assemble_revision.py 要求相邻v2原成片可用，检查105秒处关键帧、流参数和extradata，将前6300个视频包原样复制并拼接900新帧，逐包验证前段PTS/DTS/数据哈希相等。最后sync_audio.py --prepare / --apply 放入完整120秒音频，不在105秒处切音频。没有v2成片时使用上面的完整渲染路径即可。

verify_project.py 只检查工程与共享声音；仓库技能validate_delivery.py检查实际完整成片并严格解码；collect_qa.py从最终MP4抽帧、测量。browser_player_check.mjs短时浏览器播放另记；连续人工听看和真实手机App遮挡仍需真实验收。可编辑ZIP包含源码、模型、音频、字幕及紧凑QA，排除依赖、bundle、临时拼接文件和最终MP4。

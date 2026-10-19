# 后人类黑话 / THE UNTRANSLATABLE TONGUE

一眼万年 S02 EP07。120秒，60fps，7200帧；竖屏2160×3840优先、横屏3840×2160。纯代码SVG图形；所有夸张遥测与语义维度均为科幻叙事设定。

原文在../source/script.md；用户选择保留原文，持续显示科幻思想实验标识。segments.json保留原文/显示字幕/TTS输入，timeline.json与sfx_events.json共用一条帧时间轴。Q98为原分镜要求但原表格漏写的独立“别怕，都好。”台词。

依赖沿用仓库现有Remotion4.0.534/React19.1.0/TS5.9.3，node_modules为本机根目录链接，其他机器按锁文件安装。Mac本地中文字体依赖PingFang SC，字体身份记录assets-manifest.json，未将系统字体复制分发。

## 当前制作状态

原生双4K成片已导出，技术检查与归档进行中。已完成本机macOS Speech中文旁白，11段均完整放进窗口；母带5760000样本/声道，120.000秒，−17.0LUFS、−1.6dBTP。audio-timing.json基于实测PCM活动边界，字幕为按测得段长分配的句段估算，不是逐字对齐。语音合成阶段未向云端TTS/ASR发送旁白文本；源码按独立的GitHub归档授权公开留存。完整成片已导出；检查证据见 ../review/acceptance.md。

## 命令

在本目录执行npm run typecheck。Q的Mac渲染必须通过 /Users/guoq/.local/bin/agent-dev run -- node scripts/render.mjs，先核实卷身份。stills portrait <帧号...> 导出原生静帧；preview portrait <首帧> <尾帧> 导出原生运动样片。video portrait / video landscape为正式渲染，会检查全部11个实测PCM段和共享母带，缺失时拒绝运行。

本集实际配音由 synthesize_local.py 调用本机 macOS Speech；按散列复用缓存。synthesize.py 是未执行的可选云端入口，需另有当前作品的明确提供商授权，不能因脚本存在而自动调用。build_audio.py生成精确48kHz立体声120秒母带和caption估算时间，不把估算说成逐字同步。静音[5880,5910)帧=98.0–98.5秒；音符及四字从5910起。

验收：verify_project.py、仓库技能validate_delivery.py --scan-source、两版最终MP4完整解码、连续7200帧视觉筛查与可疑帧复核、LUFS/truepeak实测、字幕与手机安全区和暗部检查。人类连续听看/真实App/公开发布独立记录。成片完成后再做归档、final留存、双Release备份与恢复抽测。

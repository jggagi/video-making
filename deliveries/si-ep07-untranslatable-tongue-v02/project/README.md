# 后人类黑话 v02 · 系列配音修订

一眼万年 S02 EP07，原生双4K、120秒、60fps、7200帧。用户要求“要用这个系列一致的配音”，改回EP04/05/06已使用的百炼龙天：cosyvoice-v3-flash、longtian_v3、rate1.0；不使用v01的本机Tingting。v01及其已提交笔记保留。

原文与科幻思想实验标识保留，画面设计沿用。旁白使用新实测PCM排时；共享一份48kHz立体声120秒母带，音乐/SFX沿用确定性工程，[5880,5910)帧精确静音和5910帧四字台词保留。字幕是语义分组估计，未冒充逐字对齐。

已有仓库依赖Remotion4.0.534，node_modules为本机链接；系统PingFang字体不分发。Q的Mac重型工作通过agent-dev run并核对当前卷身份。synthesize.py是本次使用的配音入口；synthesize_local.py是旧版辅助源码，未用于v02。

命令：python scripts/synthesize.py S01或all --authorized（必须先按百炼技能完成当前任务的版本/身份检查）；python scripts/build_audio.py --audit/--mix（需已有NumPy环境）；npm run typecheck；node scripts/render.mjs video portrait或landscape。生成缓存按文本与声音设置散列，保留原始与规范PCM。

两版最终媒体完整解码、7200帧视觉筛查、手机尺度抽帧、暗部、音量和真峰值测量分别记录。人工连续听看、真实App播放与平台发布状态独立，不从自动检查推定通过。

修订合成：先运行 node scripts/render_caption_patch.mjs video portrait --output public/patches/portrait-caption-patch.mp4（横屏同理）；再运行 python scripts/compose_revision.py --portrait-patch public/patches/portrait-caption-patch.mp4 --landscape-patch public/patches/landscape-caption-patch.mp4。也可用--layout单独合成已完成的画幅。依赖的v01原生4K基础视频保存在旧交付目录及其Release，可用仓库恢复器恢复；当前工程也保留完整Composition，允许直接完整重渲染而无需基础电影。两种路径均使用本集同一新母带。

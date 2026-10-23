# EP18《心印潜流》v02 验收

本版回应“冰山能做得更像些吗”：将圆滑水滴轮廓改为双冰脊、不规则断面、细裂隙和分层冰纹。原生纯二维剖面，旧版保留。剧本、字幕与90秒时间轴不变；22个WAV逐一核对与v01相同，没有新增云端生成。

## 已完成的技术检查

- 类型检查、源码拼写扫描及13项工程检查通过。当前Scene连续执行5400帧，所有画布数值有限；源码散列与实际捕获记录对应。
- 最终MP4为2160×3840、60fps、5400帧、90.00秒，H.264／yuv420p／bt709，AAC48kHz双声道。视频、音频、容器均90.00秒；faststart与严格全片解码通过。
- 复用PCM母带−16.0 LUFS／−1.4 dBTP；成片−16.0 LUFS／−1.3 dBTP。8个编码后声画窗口通过相关性与延迟门槛。母带[81.0,81.5)秒每声道24,000样本精确为零；AAC编码后不宣称逐样本零。
- 最终MP4从头连续筛查全部5400帧，完整解码、零标记。按渲染前计划进行整幅突变与右下常暗区检查；未使用结尾消失的HUD作固定模板，也未改变阈值清除告警。筛查报告与当前MP4散列绑定。

## 模型图像观察

已查看最终编码的5张手机尺度联系表，共40帧，覆盖首尾、字幕、关键事件与8组相隔2.5秒的运动对。冰山轮廓连续、蓝色冰面和裂隙可辨；金线主动上升、冰环裂开与玫瑰展开仍清楚。字幕和结尾科学限定可读。已查看冰脊和冰肩两张750×750原生像素裁图，未观察到严重暗部色带；另看1650／2400帧的较大区域总览。封面A/B均已查看，选择A。详见model-visual-review.json、native-preview-evidence.json与iceberg-before-after.jpg。

希望留下的画面是：庞大冰山下的金色心印仍被保留，只有自愿交出的一缕金线升上海面。此为创作者与模型的表达判断，没有实际观众反馈数据。

## 尚未完成的人类与设备验收

- 人类完整连续观看与听音：待确认。
- 实际手机／小红书App播放及平台遮挡：待确认。
- 账号发布：未提交；本轮为制作与仓库归档。

自动解码、相关性与模型抽帧均不代替上述验收。

## 文件身份与报告

最终MP4 SHA-256：`9c5902c4241121140b5c1546ed1e7fdea924e822c3e4c29819edf9c517fc7657`，85,171,239字节。完整媒体验证：media-validation-20261023T093149.010174Z.json；连续筛查：visual-qc-xiaohongshu/report.json；编码后声音：encoded-audio-sync.json。测量时清单另存manifest-at-encoded-measurement.json，其后仅将最终QA状态更新为通过。

## 归档

本地final已通过APFS克隆加入，总库61份正式视频，新增1份、跳过60份。源成片与本地final散列匹配；旧31部作品清单逐项保持一致。GitHub作品归档278个资产、final备份61个资产的远端大小与SHA-256均已核对。本版作品Release含2段样片及1份正式成片；独立final Release仅1份成片。新版85,171,239字节已实际下载恢复，散列一致；重复恢复跳过匹配文件、保持inode，并清理隔离临时目录。下载抽测仅覆盖新v02，不代表历史60份均重新下载。

源码归档提交：`89fac544b917d4f550d0eb7d07ab4e0246e3090c`。

- [作品Release](https://github.com/jggagi/video-making/releases/tag/film-si-ep18-sovereign-subcurrent-v02-8272756b62fd)
- [独立final Release](https://github.com/jggagi/video-making/releases/tag/final-si-ep18-sovereign-subcurrent-v02-8272756b62fd)
- 当前总核验：`final/backup-verification.json`；本版恢复证据：`final-restore-probe.json`。

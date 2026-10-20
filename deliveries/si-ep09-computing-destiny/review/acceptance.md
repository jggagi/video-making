# EP09《被算尽的心动》验收

目标：小红书单平台，原生2160×3840，60fps，5400帧，90.00秒。关键画面、HUD与字幕保持用户指定的UI安全区；无横屏占位成片。原始台词完整保留，数值、预测和剧情为显式科幻设定。

## 已完成的制作证据

- 新方案与旧作品分目录保存，原稿/source、制作brief、四幕timeline、科学边界、发布文案和4K封面均存在。
- 8段TTS采用当前会话直接授权的百炼longtian_v3；实际返回cosyvoice-v3-flash，原始流式WAV头长度问题按真实PCM修复并保留原件、散列与缓存。未调用ASR。原始文本未更改、未偷偷加速或裁音。S01实测8.08秒，起音提前至0.4秒、8.48秒结束，原设窗口保留。
- 4条PCM音轨均48kHz/双声道/16bit、每声道4,320,000样本。最终母带−16.0 LUFS、−1.6 dBTP；[4860,4885)帧（样本3,888,000–3,908,000）全部精确为零。S08静音后起音。34条字幕最多2行、每行≤13字符，49px逻辑字号在360px预览约16.3px。详细见project-invariants.json与音频mix-manifest。
- 65项单平台/历史双平台回归测试通过；TypeScript和源码拼写检查通过。源码检查不充当媒体通过。
- 四幕原生有声短片均在真实IAB播放器加载为2160×3840，并以正常速度播到ended，无media error。模型观察了起止画面和主要动作。详见native-samples.json与representative-review.json。手机接触表曾发现并修正主体偏小、倒置心形、离开箭头方向与微扰未逐次影响路径的问题。
- 记忆画面：先画完的未来、三根牵引线、琥珀光点穿过笼子。模型自评为从温暖转入被控制的不安，再回到主动选择。此为创作者/模型判断，尚无真实观众效果证据。

## 最终媒体

正式成片SHA-256：`c9f5514809d710849f12ca4074a9f89b5e954cb25dd439b01c7f959a9641cfa1`。

- 编码媒体实测：H.264，2160×3840，60/1fps，5400帧，视频流精确90.000000秒，yuv420p，BT.709全标签，faststart。AAC为48kHz双声道，容器90.005秒；这是编码尾部填充，不是增加视频帧。见encoded-qa.json。
- 编码后音频−16.0 LUFS、−1.6 dBTP，与PCM母带波形相关度0.9999663。25帧精确数字静音属于PCM母带；AAC边界有2个PCM16单位的变换振铃（约−84.3dBFS），中段精确为零，未把有损编码边界声称为数字零。
- 最终文件完整5400帧筛查，零标记，report.json绑定本次成片散列。规则检测范围与语义观察分开记录，见visual-qc-xiaohongshu-r02/report.json。
- 模型检查了最终编码的33个时间点、三张360px接触表和原尺寸暗部/心形裁切。字幕可读；检查帧中的关键节点、HUD、字幕不侵入指定UI区域；未见严重暗部色带或分块。连续动作对照见final-visual-observation.json。
- 最终文件在真实IAB播放器加载为2160×3840，正常速度播放、章节跳转与片尾ended均成立，无media error。见player-qa.json；这不等同于连续90秒人类观看或听音。
- 第二幕未来轨迹已改为在20–24秒绘完，人物仍停在DAY001。保留初版和原生24秒重绘片段；正式版按精确帧区间替换。首次拼接因AAC末包缺失被哈希闸门拒绝，最终采用视频编码、完整音频独立封装，原/新AAC载荷SHA完全相同。见narrative-revision.md、phase-revision.json和splice-audio-failure.json。

最终严格媒体验证PASS，见media-validation-20261020T044535.239515Z.json：完整FFmpeg解码、5400帧计数、流参数、faststart、平台声明、源码扫描与绑定本片散列的全帧QC均通过。validation-provenance.json核对了当前源码输入、母带、manifest和验证报告散列。

本地final库已用APFS克隆加入正式成片，散列与原件一致；原有47份正式文件保持不变。两个上传器dry run均通过（archive：19作品/200资产；final：19作品/48正式文件）。GitHub作品归档与独立final备份均已发布并完成远端大小/SHA-256核验。整个final库48文件/19个Release独立复核通过，见根final/backup-verification.json（绑定当前backup-catalog散列）。新片从公开final Release实际下载到空AgentDev临时目录，60,904,573字节与完整SHA匹配，重复恢复正确跳过；见final-restore-probe.json。源提交为1cc5077797c0649a8c5495bdc7d636147062608b；后续证据提交不改变媒体。完整汇总见archive-verification.json。工程ZIP记录打包当时的源码与本地验收快照，后续云端回执保存在Git。ZIP有意排除电影；watch.html和samples.html需配合同一Release的独立媒体文件，或从仓库用fetch-archive-assets.py恢复原相对路径。

## 人类与设备验收

连续人类观看：NOT_RUN。人类听音/发音核对：NOT_RUN。手机及实际小红书App：NOT_RUN。模型不具备本次音频输入，不能把文件解码、音频测量或浏览器播放当成人类听音通过。传播数据/爆款成绩：NOT_RUN。

本任务制作与GitHub归档；平台账号发布不在本次执行范围。

# 巴别图书馆的尽头：验收记录

状态：技术检查、本地APFS final、GitHub作品/final独立备份和本片恢复抽测全部通过。人工与手机验收保持未执行。

## 成片与技术证据

仅小红书：2160×3840、60fps、120秒、7200帧，H.264/yuv420p/fast-start；AAC48kHz双声道。最终SHA-256：`eb2860ac3e8b7f02efc6e7862dc38184bad8c7c2176d65ecf0292c3379644d5b`。

完整严格解码、正式交付验证和源码扫描PASS。编码后响度−16.27LUFS、真峰值−1.62dBTP；与本地PCM母带抽样相关系数0.999919。连续从头筛查全部7200帧，零标记，扫描前后媒体哈希一致。详见encoded-media-qa.json、visual-qc-xiaohongshu/report.json和最新media-validation报告。

10段百炼CLI2.5.0旁白实际返回cosyvoice-v3-flash / longtian_v3；当前聊天已明确授权本片10段。配乐与音效本地程序化原创。字幕37个分句，按实测PCM活动区间加字数权重估算；未做ASR或强制对齐，不把估算称为逐字精确。

## 画面与修复

首轮线条主体偏小，改为放大包豪斯色块，保留candidate-01。第一轮全编码捕获4698帧出现真实重复文字瓦片，失败片和原始连续筛查保留在candidate-02-capture-rejected。采用同一绝对帧4698的原生Remotion重绘替换，未借邻帧、未插值、未删帧。重编码后从头重扫7200帧零标记；原生重绘与编码帧RGB平均误差1.624，已查看4697/4698/4699邻帧。证据capture-repair.json与repair-neighbors/contact.jpg。

模型已观察两轮源静帧、最终编码联系表、原生重绘和修复邻帧：主体、字幕与结尾可读，选定帧没有观察到错位或重复瓦片。这是代表画面的模型观察；筛查不能证明所有视觉或感知缺陷都不存在。

## 播放与人类验收

真实浏览器中，两段原生4K有声样片完成播放；正式修复版开始播放并使用页面控件跳到114秒，媒体无错误。片尾结束状态另见playback-check.json。该验证不等于人工连续听看。

人工连续观看、人工听音、真实手机/小红书App播放、实际观众反馈：NOT_RUN。账号未发布。

## 归档

当前文件已在本地final留存并核对SHA-256。作品清单253资产/28作品通过远端大小和SHA-256核验；独立final清单57成片/28Release通过重新获取远端清单和本地哈希核验，报告绑定当前backup-catalog。新增本片实际下载恢复成功，重复执行正确跳过已匹配文件；不把单片恢复说成全部历史影片已下载恢复。

源码提交：`72eef6e33254bb6d18e87c4833c9e4d55f806b2d`。详见archive-verification.json、final-backup-verification.json和final-restore-probe.json。

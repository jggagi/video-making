# EP12《最后一行公式》验收

状态：本地技术验收、作品Release归档、本地final、GitHub独立final备份与本片真实恢复抽测均通过。人工听看/设备验收仍待确认。

最终MP4 SHA-256：`39c3e73574ce57324f926820ffa99f7c6ba672337bca148075fc2b7cc29293c9`。

## 工程与内容

- 仅竖屏，原生2160×3840、60fps、5400帧。实际视频、音轨和容器均为90.000秒。
- TypeScript、纯2D/确定性源码检查、原始字幕拼接比对通过。全部显示原文保留；32条字幕按句段估时，不冒充逐词对齐。
- 按Q确认的方案缩写三条HUD，完整英文保存在telemetry-lexicon.json。手机360px主HUD为10px，字幕约16.3px。蓝图的次要注释为7px装饰细节。
- 八段百炼longtian_v3，CLI报告cosyvoice-v3-flash，语速1.0。S02按Q确认延伸入原留白，完整音频至21.310646秒；所有视觉/SFX关键帧不变。

## 声音实测

- PCM16、48kHz双声道、每声道4,320,000样本。母带−16.0LUFS、−1.5dBTP；最终AAC−16.0LUFS、−1.4dBTP。
- 帧[4860,4890)对应样本[3,888,000,3,912,000)，四条stem/master均精确零。笔尖事件4890，S08实测语音起点4902。
- AAC静音内部450ms仍为零；边缘25ms有编解码泄漏，前缘峰值约−111dBFS，后缘约−61dBFS。精确零保证针对PCM；最终AAC另有真实测量。
- AAC解码共4,320,256样本/声道，末端256样本为5.33ms码块填充；FFprobe音轨/容器时长均90秒。
- 三个窗口1–8、38–43、82–89秒与PCM相关系数均大于0.99993，最佳偏移均0样本。

## 捕获缺陷与最终媒体检查

首轮全5400帧筛查发现第1322帧重复HUD瓦片，已拒绝该候选。失败文件在AgentDev保留，失败报告位于candidate-01-rejected；没有把它当转场或误报清除。按同一绝对帧1322原生重绘并重新编码，未借用邻帧或插值。AAC逐包哈希一致。查看修复后1320–1324帧及邻帧，未见瓦片。

修复后最终文件从第0帧连续筛查全部5400帧，零标记、哈希前后一致；完整validate_delivery.py --scan-source通过，严格全片解码通过。报告：visual-qc-xiaohongshu/report.json、media-validation-20261021T134044.107707Z.json。

## 模型代表帧观察

查看最终编码16个代表点、8组成对运动帧、360px总览和原尺寸4020帧：开场本轮与补丁面板为平面制图，HUD无裁切；黄金机械汇聚与字幕分区清楚；4859→4860后网格/标尺消失，单点与细金圈保留。主要空间运动可见；暖白平面未见严重色带。本片没有暗部渐变镜头。详见representative-review.json。

创作目标：精密而繁杂的图纸最终成为孤独的一个点，从“理解一切”的满足转向怀念未知。这是创作意图与模型画面观察，实际观众感受尚无证据。

## 发布附件与科学设定

A/B封面分别来自最终编码4020/5040帧，另有原生标题版；文案、标签、文件哈希见小红书/publish-package.json。账号提交NOT_STARTED。

本片是科幻思想实验。终极统一、128bits和未知为零均为叙事设定；δS=0为变分原理示意。原文历史简化保留并在scientific-notes.md说明。画面限定只在5160–5400帧、透明度0.35出现。

## 人工与设备

- 连续人工听看：NOT_RUN。
- 人工发音/情绪试听：NOT_RUN。
- 真实手机/小红书App播放：NOT_RUN。
- 实际观众体验反馈：NOT_RUN。

技术通过和模型抽帧观察不能替代以上验收。

## 本地final与归档预检

本地final库新增本片APFS克隆，53份正式历史/本次成片逐项验证；新片路径为final/si-ep12-final-equation/小红书/si-ep12-final-equation-xiaohongshu-90s-portrait.mp4。作品总清单231个资产、final清单53个资产默认dry-run通过。GitHub上传、远端核验和本次新增成片恢复抽测均已完成。

## GitHub留存与恢复证据

源码提交：b2c764444d39b7ecd1132766b4fa38d8c97ea700，已push。

- 作品Release：https://github.com/jggagi/video-making/releases/tag/film-si-ep12-final-equation-9693cfcbd26b
- 独立final Release：https://github.com/jggagi/video-making/releases/tag/final-si-ep12-final-equation-9693cfcbd26b
- 作品清单231资产/24作品远端大小与SHA-256核对通过，见archive-verification.json。
- 当前final清单53成片/24 Release本地与新远端清单逐项核对通过，记录位于仓库final/backup-verification.json，并绑定当前backup-catalog散列。
- 本片新final在隔离AgentDev目录真实下载恢复，59,049,637字节与SHA-256一致，第二次执行跳过匹配文件，临时恢复目录已清理。仅这一新增影片实际下载恢复，不能表述为全部历史影片均已恢复。详见final-restore-probe.json。

编码后45.833秒处另抽帧确认变分恒等式可见，证据encoded-equation-2750.png。

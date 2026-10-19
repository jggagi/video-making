# EP07 v02 系列配音修订 · 技术验收通过

用户要求“要用这个系列一致的配音”。核对EP04/05/06成功缓存后，本版11段均使用百炼cosyvoice-v3-flash、longtian_v3、rate1.0。v01的Tingting是错误选择，原版保留。CLI/技能/npm均2.4.0；未使用ASR。

原文和全片科幻思想实验标识保留。S02按10.56秒实测源音频提前至第600帧；所有非零语音完整保留，无后期加速。Q98首个保留非零样本位于第5910帧，RMS活动边界延后170样本。

48kHz立体声PCM母带每声道5,760,000样本、120秒、−17.0LUFS/−1.6dBTP；所有stem与母带在[5880,5910)帧精确为零。25组字幕按实测段长和字符权重估计，不是逐字ASR对齐。

两版最终原生4K、60fps、7200帧、120秒；完整严格解码、源扫描和项目不变量全部PASS。两版连续7200帧孤立跳帧筛查均0标记，未启用静态ROI检测；不将其解释为全像素完美。最终文件均−17.0LUFS/−1.5dBTP，抽测2/44/98/116秒音频与新母带最小相关性0.999912455。

模型已检查实际最终文件的两版联系表、13组场景对、竖屏960帧、横屏6600帧、原生暗部光晕裁片，以及此前原生字幕接缝/动态合成短样。抽查未见字幕位移、截字、明显字幕补丁接缝或突兀光晕边界。native暗部裁片位于/private/tmp/ep07-v02-{portrait,landscape}-native-glow.png。旧主画面经新字幕带覆盖和H264再编码，未声称像素无损。

完整证据见final-media-evidence.json、visual-qc-*/report.json、media-validation-20261019T175449.370711Z.json、patch-source-comparison.json、patch-motion-preview.json。

人工连续听看、真实手机App播放和观众反馈未执行。小红书原笔记已提交视频修订，管理页显示审核中、仅自己可见，笔记数仍为8；归档状态另见publication-record.json和archive-verification.json。

本地final两份APFS克隆完成；GitHub作品Release全部9项、独立final Release两份成片大小与SHA-256匹配。当前final清单17个Release/45份文件全部核验；新版竖屏实际下载恢复与第二次匹配跳过通过，临时恢复数据已清理。这是单文件恢复抽测，不代表全部45份均下载恢复。源码提交6937cd8646c4ac60a289d3f84550708af2d80aa4。

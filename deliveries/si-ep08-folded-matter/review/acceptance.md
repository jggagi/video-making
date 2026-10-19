# EP08《被折叠的造物》验收

本地技术制作、源码推送、作品Release、独立final备份及恢复抽测均完成。逐轮捕获与修复经过见iteration-history.md，旧报告只代表对应历史散列。

## 最终成片

两版均原生4K、60fps、7200帧、视频/音轨/容器120.000秒，H.264 / bt709 / yuv420p，fast start通过。竖屏2160×3840；横屏3840×2160。最终散列见final-media.json。

| 项目 | 状态与证据 |
| --- | --- |
| TypeScript、确定性源码、帧时间轴、HUD拼写、字幕边界 | PASS，源码修改后重新检查 |
| 最终完整严格音视频解码及规格 | PASS，review/media-validation-20261019T175433.551609Z.json |
| 从0连续覆盖全部帧的视觉筛查 | 两版各7200帧，零标记；竖屏r05、横屏r03 |
| 最终AAC与PCM母带 | PASS，review/shared-audio-correlation-r04.json；两版解码PCM散列相同 |
| 模型最终编码代表帧/手机预览/暗部/运动/修复邻帧 | 已实际观察，final-frame-review.json |
| 人工完整观看、发音与混音试听 | NOT_RUN |
| 真机及小红书App遮挡、平台压缩 | NOT_RUN |
| 实际观众情绪与复述反馈 | NOT_RUN |
| 本地final、GitHub作品与独立final备份、恢复抽测 | PASS，archive-verification.json / final-backup-verification.json / restore-probe.json |

报告生成后仅更新delivery.json的qa完成状态；技术参数、源码及媒体均未变化。验证时的清单原件保留，final-manifest-binding.json记录前后散列与唯一差异。

## 声音

用户明确授权本期百炼longtian_v3，实际CLI返回cosyvoice-v3-flash / longtian_v3，共10段缓存；CLI与已安装百炼技能均经授权升级至2.4.0。没有云端ASR或额外图像/视频生成。

共享母带48kHz、立体声PCM16、每声道5760000样本，SHA-256 `c8f5d0914e0b8ec621d6fbcd23114887b342dde1e5da9327eeff9cac3610735d`。母带和两版最终AAC均−17.0 LUFS / −1.8dBTP；一份AAC缓存复制到两版，各次画面修复逐包验证音轨不变。

全部stem及母带在[5880,5910)即[4704000,4728000)样本精确为零，钛滴从5910开始。AAC变换窗在边缘存在极低能量：峰值7/32768、RMS约−96.51dBFS，98.06–98.44秒内部精确为零；未将有损编码边缘写成整段数字零。最终端点PCM为[0,0]。

旁白及所有cue未裁剪或拉速。配乐在人声实测区间降低6dB，提前60ms、释放350ms；音效1.4kHz和2.8kHz各降低9dB；118.5–120秒淡出。原mix-v01留存。40条自然短句字幕按实测PCM窗口估计句内时序，非逐字强制对齐；双平台SRT一致。

## 画面与内容

记忆画面是方钢被青色路径掏空、留下金色多孔骨架。最终两版16帧总览、各18组成对帧、原尺寸暗部裁切、360px竖屏预览及引句/修复边界均已查看。主体透视、孔隙、城市尺度与节点位置有空间变化；5100/5250比较段运动较轻，正常速度的体感与节奏仍需人看确认。未把HUD计数或字幕切换当作运动证明。

原稿完整保留。原九段旁白及HUD数字保留为科幻设定，持续标示FICTION及非工程实测，片尾S10补充载荷、材料、制造约束。所有结构、应力色带和破坏是程序化视觉示意，没有运行工程有限元/流体求解或真实承载试验；详见project/scientific-notes.md。

实际捕获曾出现重复文字瓦片，已按相同绝对帧原生重绘；最终不是靠调阈值、借邻帧或删除标记通过。引句窗口的通用章节文字重叠已在源代码消除。失败片/中间片本地留存，未进正式归档；840张可再生PNG已核验后清理，保留代表帧、全量散列、修复及复扫证据。未隔离浏览器捕获偶发异常的唯一根因，零标记也不等于人类连续观看无瑕疵。

本次没有账号发布授权。branding及EP07并行修订不纳入本片源码提交。

## 归档与真实恢复

源码提交：`a707ebe84022da569707eaac9851be0cbd77b59c`，已正常推送main。作品Release：<https://github.com/jggagi/video-making/releases/tag/film-si-ep08-folded-matter-fb067a56db5a>，13个资产（两版正式成片、10份原生预览、工程ZIP）大小与SHA-256均经远端核验。工程ZIP为打包时快照，530个成员逐一CRC及散列通过；云端归档完成后的补充证据在Git中保留，未覆盖已上传ZIP。

本地final创建两份独立APFS克隆并核验，保留此前45份历史成片。独立final Release：<https://github.com/jggagi/video-making/releases/tag/final-si-ep08-folded-matter-fb067a56db5a>，本片两版均已核验。全局当前47个final资产的本地散列、远端字节数、SHA-256与当前备份清单一致，报告绑定清单散列。

从本次新增竖屏final实际下载169,658,525字节到隔离临时目录，恢复相对路径及SHA-256 `65c2f5d25ec86e72fbaedf4b619e8eb7c4d82c760c1c8ed829a7736650a1ff88`均一致；第二次恢复验证跳过匹配文件。临时文件已清理。这是一份新增成片的下载恢复抽测，不是全部47份都下载恢复。

人工连续观看、配音/混音试听、真机App及观众体验仍为NOT_RUN，没有账号发布操作。

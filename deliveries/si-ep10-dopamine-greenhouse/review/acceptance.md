# EP.10《多巴胺温室》验收

当前阶段：原生4K正式成片已完成媒体、完整5400帧复扫、最终编码帧与声音技术验收；归档核验进行中。以下状态不得用源码通过推定媒体通过。

## 已完成的源码与画面检查

- 通过仓库初始化器建立小红书单平台清单：2160×3840、90秒、60fps、5400帧；原稿散列已锁定。
- TypeScript严格类型检查通过；八段显示与发音文字分离。确定性扫描、字幕分片全文还原与每行≤13中文字检查通过。
- 360px代表静帧已经实际观察：眼睛、奖励花、茧与尖角、蜂巢、62秒同沙发双人、饱和、全黑、石头与火星。首次观察发现飞入形体靠近限定说明，已将前景裁切到x64..908、y470..1280；修正后重验。字幕阅读带由独立源码审查发现锚点略偏高，已改为y1384、行高54，保持双行底边1492小于安全区起点1497.6。
- 顶部三条HUD保留用户完整常量，通过裁切框内的慢移呈现；字号30逻辑px，手机360宽有效10px。字幕字号49逻辑px，有效16.33px。字幕主区域y1384..1492，低于底部UI起点1497.6；右侧关键内容最大x908，小于14%保留区边界928.8。
- 帧4860为白线，帧4861..4890全黑；界面、HUD、标题、字幕在黑场全部消失。实际最终编码仍待全帧验证。

## 当前待完成门槛

| 层次 | 状态 | 说明 |
| --- | --- | --- |
| 旁白授权 | AUTHORIZED | 用户2026-10-20直接设定默认授权百炼longtian_v3；已写入仓库和安装技能，八段文本哈希绑定。 |
| 原始旁白与90秒PCM | TECHNICAL_PASS | 八段实际cosyvoice-v3-flash/longtian_v3，完整PCM不变速/裁字；4320000样本/声道、48k双声道，-16.0LUFS、-1.5dBTP；30帧PCM零、Click保留。见audio-qa.json。 |
| 带真实旁白的代表片段 | MODEL_OBSERVED / BROWSER_PLAYBACK | 五段原生4K样片；四段在IAB完整播放0..3.008秒，含正式母带。代表编码帧联系图已观察，见representative-review.json。此层不替代人工听音。 |
| 4K最终MP4与媒体验证 | PASS | 2160×3840 H264/yuv420p/BT709、60fps、5400帧、视频90.000秒；容器/AAC90.005秒，faststart与全片严格解码通过。 |
| 5400帧连续视觉筛查 | PASS | 首轮发现1369/4043两帧真实瓦片错误，失败原片和报告保留。按原始绝对状态原生重绘两帧后，新文件从零重扫5400帧，标记0；report r02绑定当前散列。 |
| 最终AAC响度/真峰值/同步 | PASS | -16.0LUFS/-1.5dBTP；修复保留全部4221AAC包且ADTS散列相同；与PCM波形相关0.9999603。PCM30帧全零；AAC边缘约-59.4dBFS振铃，剔除两端各2帧后中央为零。 |
| 浏览器播放与跳转 | PASS | IAB原生4K影片完整播放0..90.005秒，ended为true且无media error；“同一沙发”按钮跳转62秒且暂停，见player-qa.json。 |
| 人工完整听看 | NOT_RUN | 不以模型图像观察代填。 |
| 真实手机小红书播放 | NOT_RUN | 安全区基于制作规范，App遮挡需实机观察。 |
| 本地final与GitHub双备份 | IN_PROGRESS | 媒体验收已通过；将建清单、提交push、两份Release上传并核对远端大小/SHA256及新增影片恢复。 |

## 科学与体验边界

画面持续标明“未来SI思想实验·遥测与数值均为虚构”。IRL为概念隐喻，未运行模型；多巴胺百分比、延迟、瞳孔数值与认知光年均为虚构仪表或叙事尺度。详见project/scientific-notes.md及其中原始论文。

模型代表帧观察：同一沙发、各握手机、相背的人与独立椭圆茧的关系可辨。静帧本身不能证明指数拉远、金属融化与声音转折在连续播放中有效；无观众反馈，不推定情绪共鸣或传播量。

## 本机执行环境

已读取`/Users/guoq/Developer/agent-workstation/README.md`并实时核验外置盘身份：AgentDev APFS UUID F4DCCF30-ED44-4B5E-8DF9-ED2C039F2857；WD_BLACK UUID 7E4BC5BA-F525-344A-BECE-08C3272BB25B。开始时AgentDev约106GiB、WD_BLACK约257GiB空闲，内部约1.4GiB（警告项）。渲染bundle与可重建临时文件在AgentDev，未删除或移动现有作品与并行branding目录。

无新增依赖安装。现有Bundled Python `/Users/guoq/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`可用NumPy2.3.5/Pillow12.3.0；默认python3没有NumPy，不能直接用它运行音频混音和视觉扫描。技能frontmatter用已有Node js-yaml核验；Python官方quick_validate因缺PyYAML未执行，没有为此安装依赖。百炼协议、CLI与npm最新版本均已核验为2.4.0。

正式影片SHA256：`2241fd76ba65c08758a84813f0f13bbe125f1d5ca6f868a090e56e85e44323b0`。原生重绘PNG已经作为正式源资产写入project/public/repair-frames并将保存在Git/工程包；源失败电影只留本地诊断，不列为正式影片。修复采用二次H264编码，记录其有损重编码限制；原AAC逐字节保留。

工程ZIP为上传前的源与QA快照；云端上传、最终备份和恢复闭环记录随后在Git中补齐，以最新Git验收及archive-verification.json为准。

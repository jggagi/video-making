# v03 闪烁诊断与修复范围

用户报告v02小红书版“一闪一闪”，并要求氛围背景音乐。旧版媒体和源码保留。

## 实际编码证据

对旧竖版从文件起点连续解码全部7200帧（无快进取帧），稳定水印区域筛查得到81帧模板异常、160个相邻跳变边沿（包含恢复帧），总标记161帧。高排名10张图中可见原本不属于画面的重复文字拼贴。Root另核对第889帧：它只显示多行重复HUD，888/890帧正常。旧横版第894帧亦有拼贴；连续解码与快速定位得到该帧的RGB散列相同，排除了本次取帧的寻址启动伪影。参见`flicker-before/temporal-scan.json`、`frame-confirmation.json`和原编码散列绑定的`metrics.json`。

这属于实际编码里的画面缺陷。前次严格解码能确认码流可解，稀疏抽帧没有覆盖这些间歇坏帧；原先人工连续观看状态一直是待确认。本次保留用户真实反馈，不把先前自动检查当成视觉无误。

## 修复与解释的边界

v03通过工程局部Chrome启动脚本禁用GPU rasterization/GPU，Canvas使用CPU backing，帧中间件改为无损PNG；原生双4K仍直接栅格化。没有改动系统Chrome配置、用户浏览器profile或依赖版本。旧版横版894和竖版889的重复拼贴，在同位置的新版原生4K样片中消失；带真实字幕、旁白和音乐的竖版连续样片也已观察。现在两版最终编码均有独立严格解码和全7200帧扫描记录，细节见下文与`media-validation-20261019T125004.201271Z.json`。

### v03 首轮竖版全片捕获

首轮完整竖版 CPU/PNG 捕获仍出现重复瓦片坏帧，索引为 `138, 142, 147, 149, 153, 164, 3842, 3853, 3857, 6928, 6992`（均为从零开始的帧号）。失败片保存在 `iterations/portrait-initial-capture/`。这次捕获使用了项目级禁用 GPU/GPU rasterization 的 Chrome 启动器和 PNG 中间帧。捕获后，`project/src/Film.tsx` 加入字体就绪门：等待 `document.fonts.ready`，再等待两次 `requestAnimationFrame`，才继续渲染。该就绪门对后续完整编码的影响尚未由全片扫描确认。

`project/frame-repairs/portrait/` 中的十一张替换图分别来自相同原生4K画布、相同绝对帧状态的独立重绘；没有插值或借用邻帧。`project/scripts/repair_frames.py` 将覆盖限定在指定的零基帧号，另写新 MP4 和 JSON 报告，不改输入；视频以 CRF 15 重编码，音频包复制并逐包校验 SHA-256 一致。修复后的竖版最终编码已连续解码全部7,200帧；窄筛查区域未产生标记。

### 最终编码筛查与转场复核

竖版`flicker-after-portrait/temporal-scan.json`记录连续解码7200帧、0个标记。横版`flicker-after-landscape/temporal-scan.json`记录连续解码7200帧，原始筛查在2600和5400各标记一个水印ROI相邻帧跳变。`landscape-transition-review.json`绑定横版SHA并记录两处前后共六帧：2600开始持续的热色调，5400发生持续的第三至第四章节/地球热景到深空背景切换；目标帧后的画面状态分别持续，没有重复瓦片或孤立闪帧。对应图为`landscape-transition-2600.jpg`和`landscape-transition-5400.jpg`。

两个筛查器都只覆盖缩小后的固定ROI和保守启发式规则，不能证明整幅画面无缺陷，也不替代连续人类观看。`media-validation-20261019T125004.201271Z.json`对两版的源清单、规格及严格音视频解码均报告PASS；`project-check.json`亦为PASS。模型辅助取样观察另记在`visual-observations.json`，不等同人工验收。

可确认的是首轮编码文件中实际存在重复瓦片，最终竖版的窄ROI扫描为零标记，横版两个原始标记经相邻帧复核后对应持续的源定义转场。禁用 GPU/GPU rasterization、Canvas CPU backing、PNG 中间帧和字体/绘制就绪门是捕获路径的确定变化；这些证据尚未隔离唯一底层原因，尤其不能证明 GPU 栅格路径就是根因。GPU 因果归因仍是推断。

Remotion当前源码对Lambda的相似重复条带问题使用了`--disable-gpu-rasterization`。维护者的[一手问题记录](https://github.com/remotion-dev/remotion/issues/11428)提供同类栅格缓存问题的依据；本机不是Lambda环境，本次没有把操作系统/驱动级原因隔离成单一开关，故底层归因是推断。实际可证的是旧编码有重复拼贴、修订捕获路径下相同帧恢复正常。另参考[官方闪烁排查](https://www.remotion.dev/docs/flickering)。

同时消除不舒适的高频设计：去掉900f约19Hz整块抖动与每90帧重复重置的冲击环；光束/热流/碰撞采用平滑出入、较缓运动，晶格低对比，散热光子使用稳定分支种子。这些是额外的观看舒适度修订，与拼贴坏帧分开记录。

## 声音

完整120秒共享PCM重新混入本地原创和弦/低弦/晶体音，所有十段旁白逐文件复用。精确48kHz双声道、每声道5760000样本，−17.0LUFS、−1.8dBTP；5400–5424帧仍为数字零。音乐220–1200Hz层有实际频带测量，参见`music-qa.json`；不能据此代填手机外放或人工听感接受。

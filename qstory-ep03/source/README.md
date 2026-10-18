# 余问 QStory｜EP.03 制作交接包

## 已提供

- `EP03_director_brief.md`：完整180秒导演稿、24镜头、8场景、美术与声音设计、Remotion工程约束。
- `EP03_timeline.json`：30fps的单一时间轴，场景/镜头/字幕/静音窗口与资料来源。
- `EP03_narration_zh.txt`：可交给真人或TTS录制的中文文案。
- `EP03_zh_planned.srt`：计划字幕，录音后须重对齐。
- `CODEX_TASK.md`：给本机Remotion Skill/编码Agent的执行任务。
- `validate.py`与`validation_report.txt`：时间轴/字幕等元数据验证及结果。

## 未提供

这不是完整React工程或已渲染视频。不含MP4、配音、音乐、外部影像、字体文件；没有宣称完成Studio、WebGL或音画验收。

本包供制作与编码交接使用。`python validate.py`仅验证本包结构和时间边界，不会验证未来实现代码。

制作顺序：先做110—145秒高潮预演 → 全片灰模 → 录音/配乐 → 美术打磨 → 竖版布局。

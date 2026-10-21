# Historical scaffolding notes

These notes describe the initial unrendered state. Current results are in review/acceptance.md and 小红书/publication-record.json. The generated archive indexes supersede the old links and pending statements below.

# 逆转的沙漏 · 留住这一根白发 v02

This is the revised Xiaohongshu portrait edition of EP11. Its declared target is native 2160×3840 at 60 fps for 90 seconds (5,400 frames). The source script is preserved byte-for-byte from v01, with its raw SHA-256 in `delivery.json`.

The current delivery status is pending. The manifest keeps automated media QA, representative-frame review, continuous human review, and target-device playback separate. Generated or model-inspected frames do not establish continuous viewing, listening, audience feedback, or phone/App acceptance.

Project implementation and lightweight source/audio checks are documented in [project/README.md](project/README.md). The review checklist and evidence fields are in [review/acceptance.md](review/acceptance.md).

## Final validation and archive commands

After the final MP4 exists, run the continuous frame scan from the repository root to create the required report:

```sh
python3 skills/dual-platform-video/scripts/scan_visual_qc.py \
  --media deliveries/si-ep11-kintsugi-ink-v02/小红书/si-ep11-kintsugi-ink-v02-xiaohongshu-90s-portrait.mp4 \
  --expected-frames 5400 \
  --output-dir deliveries/si-ep11-kintsugi-ink-v02/review/visual-qc-xiaohongshu
```

Then run the complete delivery validator, including strict decode and the hash/frame-coverage checks for that report:

```sh
python3 skills/dual-platform-video/scripts/validate_delivery.py deliveries/si-ep11-kintsugi-ink-v02 --scan-source
```

Once final validation passes, build and inspect the repository archive catalog:

```sh
python3 scripts/build-archive-catalog.py
```

The catalog builder blocks this new edition unless its required visual-QC evidence is complete. Follow [the archive workflow](../../skills/dual-platform-video/references/github-archive.md) for the subsequent dry-run, scoped source commit, upload, and remote hash verification. These commands are documentation only; no render, scan, upload, or account publication is performed by this scaffolding.


# EP11 v02 小红书发布文案

## 当前状态

**PLANNED — 待完成成片与素材 QA；尚未替换或发布。** 依照既有授权，QA 完成后更新现有笔记，不新建重复笔记。排期计划为 **2026-10-21 08:00（GMT+8，北京时间）**。目标笔记 ID：`6ad78f82000000002900e27f`。这里记录的是计划，不代表平台操作、审核通过、定时状态或公开可见性已经验证。

## 发布文案

- 标题：`如果永远年轻，白头偕老还算誓言吗？`
- 可编辑正文：[`post-caption.txt`](post-caption.txt)，正文 519 个汉字；含标点与段落换行共 587 字符，标题与话题分区，话题发布时逐项选择，不把话题词混入正文。
- 话题（保持既有九项）：超级智能、抗衰老、白头偕老、数字金缮、科幻美学、数字艺术、深度思考、时间、一眼万年。
- 内容声明计划：笔记含 AI 合成内容；可见性计划：公开。

正文明确标注这是科幻思想实验，并说明人体全身逆龄与永生尚未实现。关于衰老、部分重编程及其未解风险的措辞按 [`project/scientific-notes.md`](../project/scientific-notes.md) 校对。掌纹峡谷、瓷雨逆行与金色修复河均为艺术隐喻；没有写成医疗建议、疗法承诺或记忆消除。

## 本版素材与证据路径

- 最终竖屏视频（待成片、QA）：[`si-ep11-kintsugi-ink-v02-xiaohongshu-90s-portrait.mp4`](si-ep11-kintsugi-ink-v02-xiaohongshu-90s-portrait.mp4) — **尚不存在；** 预期路径来自 [`delivery.json`](../delivery.json)。
- 封面（待选、核对）：[`cover.png`](cover.png) — **尚不存在；** 使用前须将实际封面与路径记入交付记录。
- 可编辑发布正文：[`post-caption.txt`](post-caption.txt)。
- 当前笔记与授权/排期计划记录：[`publication-record.json`](publication-record.json)。
- 原始剧本：[`source/script.md`](../source/script.md)；改编稿：[`project/adapted-script.md`](../project/adapted-script.md)；科学边界：[`project/scientific-notes.md`](../project/scientific-notes.md)。
- 项目字幕：[`project/public/audio/captions.srt`](../project/public/audio/captions.srt)。
- 媒体验收清单与证据位置：[`review/acceptance.md`](../review/acceptance.md)；代表帧、连续视觉扫描、音画检查报告应保存于 `../review/` 中相应路径。

## 剩余门槛

1. 生成最终视频与封面，并核实实际文件路径及版本。
2. 完成该版本的自动媒体检查、代表帧复核、连续正常速度观看/聆听及目标设备播放；只记录实际执行并有证据支持的结果。当前验收清单中的这些项目仍为待执行。
3. QA 完成后，在平台确认目标笔记 ID 与账号，核对视频、封面、正文、九项话题、AI 内容声明及 GMT+8 排期，再按既有授权替换该笔记。
4. 记录平台实际返回状态与北京时间排期；发布后另行核实审核/公开状态。未核实前不得将其标为已提交、审核通过、已发布或公开可见。

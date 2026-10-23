# EP16 干声旁白 A/B 试听

两份文件都按 S01 → S08 → S09 的顺序完整串接，段间各留 0.8 秒静音。没有配乐、EQ、压缩、变速或旁白裁剪。

- [试听 A](audition-A.wav)
- [试听 B](audition-B.wav)

两份均为 48 kHz、单声道、PCM16 WAV。根据完整串接输入的 EBU R128 测量结果，使用共同目标响度和每组各自的恒定线性增益；输出阶段只做恒定音量调整与 FFmpeg SWR 高质量重采样（64-tap filter、精确有理比、0.97 cutoff），不使用动态 loudnorm 或 limiter。
共同目标响度：-23.41 LUFS；最终实测 A=-23.43 LUFS / -1.60 dBTP，B=-23.41 LUFS / -4.56 dBTP。

试听限制：这是制作配置对照，不是严格的模型控制实验。两边音色不同，Qwen 生成使用了逐段表达指令，CosyVoice 使用既有系列干声；音色和指令均可能影响听感。两边旁白文本相同，原始片段完整保留。自动完整性与响度检查已运行；人工听感验收尚未执行。

## 先听后揭晓

下面会显示 A/B 与生成来源的对应关系。

<details>
<summary>展开映射</summary>

- A：CosyVoice
- B：Qwen

增益与每组输入分析值保存在 `comparison-key.json`。分段位置、SHA、样本数与验证结果见 `qa.json`。

</details>

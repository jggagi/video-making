# EP16《零摩擦人间》验收

仅小红书，原生2160×3840 /60fps /7200帧 /120.000秒，H.264/yuv420p/BT.709/faststart，AAC48kHz立体声。正式SHA-256：`299b91acdabaed526c027f8268a350cfa4e0832a2dc16a925d7ed4176cecd690`。

技术检查通过：原稿哈希、源码术语、精确帧数/时长、九段语音未裁切/未倍速、字幕全文及边界、严格整片解码。PCM每声道5760000样本；母带−16.0LUFS/−1.4dBTP，最终AAC−16.0LUFS/−1.3dBTP。字幕为实测语音活动区间内的分句估时，不宣称逐词强制对齐。

标准连续视觉筛查与白底空白区域连续筛查均覆盖最终7200帧、零标记，绑定本次SHA。白底检测新增于发现旧通用检测漏检之后；它不是所有像素缺陷均被排除的证明。

处置：手掌SVG坐标缺分隔符，原生重绘帧5580–6359；22帧重复页眉瓦片，逐项查看前后候选并同帧原生重绘。索引均用新FFV1五帧测试验证，不借邻帧、不插值、不删帧。AAC包摘要完全保留。旧候选保留candidate-01/02；见hand-path-correction.json、hand-redraw-composite.json、tile-repair.json。旧候选技术PASS不作为最终视觉验收。

模型已查看最终编码22修复帧、首尾/转场代表帧、长镜头2.5秒主体对照和原生尾幕；字幕手机尺度清楚，悬滴、松手、涟漪可辨，白底无大面积暗渐变，未观察到严重色带。感受与直觉是模型自评，真实观众反馈未采集。

连续人工观看、人工听音、真实手机/App播放：NOT_RUN。

本地final：PASS，APFS克隆和正式成片大小/哈希一致。

归档完成：源码提交c6c7e8b93c562a94b91c1583877c6cf20f335e1e已推送；作品Release5资产、独立final Release1正式成片，远端大小/SHA-256匹配。全final目录29个Release/58文件实时核验通过。新增EP16实际下载恢复一次、第二次跳过匹配文件；不代表历史影片全部重新下载。详见github-film-verification.json、final-restore-probe.json及根final/backup-verification.json。

小红书：Codex执行一次最终提交后，先观察到“审核中”，随后在“已发布”选中列表核对到本集标题、02:00及自定义封面。页面时间原文2026-10-23 00:02，时区未注明。submission_verified=true，publication_verified=true；独立公开访客及手机App可见性未测试，public_visibility_verified=false。截图保留在私有临时目录，其SHA-256记入publication-record.json，不上传Git或Releases。未重复提交，未安排后台轮询。

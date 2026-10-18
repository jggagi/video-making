# GitHub 归档与后续同步

Q 已明确要求：把本技能、当前视频工作区的所有历史短片、之后使用本技能制作的作品，都归档到
[jggagi/video-making](https://github.com/jggagi/video-making)。这项授权覆盖相关源码的提交/push 和该仓库的 Release 媒体上传；不覆盖 B站/小红书账号发布、仓库可见性变更或无关个人文件上传。

## 位置与结构

Q 本地 Mac 的现有仓库位于 `/Users/guoq/Documents/ChatGPT/video`。先验证该目录的远端仍为用户指定的仓库，不能移动或覆盖现有工程。其他机器使用对应检出的仓库，不套用本机绝对路径。新作优先在该仓库的 `deliveries/<作品版本>/` 完成；用户指定其他输出位置时，先保留原件，再把该作品的必要工程与交付物按明确路径复制并校验到仓库，排除凭据与无关文件。

- Git 保存 `skills/`、可编辑源码、原始剧本/改编稿、锁文件、本地创作素材、字幕、精简 QA 和作品索引。
- 成片 MP4/MOV/WEBM 与工程 ZIP 保存到**同一仓库的 Releases**。每部作品/版本一个独立 tag；`deliveries/<作品版本>/B站/` 和 `小红书/` 的索引提供对应下载链接。本机视频仍留在原交付目录。
- 历史作品使用 `deliveries/legacy-<作品>/`，记录原版实际参数，不能为套用新技能擅自改成120秒或伪造不存在的竖屏版。
- `archive/catalog.json` 记录每个资产的原路径、Release 文件名、字节数、SHA-256、实测画面参数与下载 URL。所有可恢复文件均保留原来的工程相对路径。
- 作品和平台的索引 README、`archive.json`、总清单由脚本生成；创作说明写在 `project/brief.md`，人工验收写在 `review/acceptance.md`，不要把手写内容放入生成索引。归档器保留并单列工程内的视频素材，不能将背景片段误列为最终平台成片。

## 每次完成作品后

1. 完成原有技术检查，保留人工/真机待验收状态。把新作的 `delivery.json`、源码、素材及 QA 一起归档，不能只上传视频。
2. 在仓库根运行 `python3 scripts/build-archive-catalog.py`，检查作品/平台归类、源文件哈希和待上传集合。生成的历史索引不改动原始媒体；新作的两个视频必须已达到120秒规格。
3. 用本技能的 `scripts/upload_releases.py --catalog <仓库>/archive/catalog.json --root <仓库>` 做只读本地预检。默认不联网上传；它会检查文件与清单是否匹配。
4. 检查变更范围，按本作品、技能及清单的具体路径提交；排除凭据、依赖、bundle、日志与无关并行修改。正常 push 到该仓库，不 force、不重写旧历史。确认远端含本次 commit。
5. 用相同 uploader 加 `--apply --target <已push的完整commit SHA>` 上传。先创建 draft Release，再逐文件上传并核对远端大小及 SHA-256 digest，全部通过后公开该 Release。不得在上传不完整时声称归档完成。
6. 如遇中断，修复实际原因后重跑同一清单；已验证相同内容会跳过。遇到同名但哈希不同的远端文件，保留旧文件并使用新作品版本/tag，不能 `--clobber`。
7. 交付时同时提供本地两版视频、GitHub commit、作品 Release 链接及远端核对结果。只有本地 commit、push、Release 上传全部成功，才说“已同步到 GitHub”。

用户以后调用本技能制作新片时，继续执行此同步约定。没有新作品产生时不创建后台任务、定时器或无关提交。上传失败时保留本地交付与可续传状态，明确报告实际剩余项。

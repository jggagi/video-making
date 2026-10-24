# GitHub 归档与后续同步

Q 已明确要求：把本技能、当前视频工作区的所有历史短片、之后使用本技能制作的作品，都归档到
[jggagi/video-making](https://github.com/jggagi/video-making)。这项授权覆盖相关源码的提交/push 和该仓库的 Release 媒体上传；不覆盖 B站/小红书账号发布、仓库可见性变更或无关个人文件上传。按 Q 于 2026-10-23 更新的分工，小红书只交付本地发布包，由用户自行上传和发布；取消平台代发不影响这里的 GitHub 源码、作品及 final 备份归档。

## 位置与结构

Q 本地 Mac 的现有仓库位于 `/Users/guoq/Documents/ChatGPT/video`。先验证该目录的远端仍为用户指定的仓库，不能移动或覆盖现有工程。其他机器使用对应检出的仓库，不套用本机绝对路径。新作优先在该仓库的 `deliveries/<作品版本>/` 完成；用户指定其他输出位置时，先保留原件，再把该作品的必要工程与交付物按明确路径复制并校验到仓库，排除凭据与无关文件。

- Git 保存 `skills/`、可编辑源码、原始剧本/改编稿、锁文件、本地创作素材、字幕、精简 QA 和作品索引。
- 成片 MP4/MOV/WEBM 与工程 ZIP 保存到**同一仓库的 Releases**。每部作品/版本一个独立 tag；新作默认只在 `deliveries/<作品版本>/小红书/` 生成对应下载索引；历史 `B站/` 索引及明确新增平台按各自清单保留。本机视频仍留在原交付目录。
- 历史作品使用 `deliveries/legacy-<作品>/`，记录原版实际参数，不能为套用新技能擅自改成当前目标时长或伪造不存在的竖屏版。
- `archive/catalog.json` 记录每个资产的原路径、Release 文件名、字节数、SHA-256、实测画面参数与下载 URL。所有可恢复文件均保留原来的工程相对路径。
- 作品和平台的索引 README、`archive.json`、总清单由脚本生成；创作说明写在 `project/brief.md`，人工验收写在 `review/acceptance.md`，不要把手写内容放入生成索引。归档器保留并单列工程内的视频素材，不能将背景片段误列为最终平台成片。
- Q要求另有统一的final成片备份：本地 `final/` 按作品版本/平台保存实际文件；GitHub `final/` 保存索引与恢复清单，实际视频另上传到专用的每作品 `final-*` Releases。它们是独立的云端final资产，不改变原作品Release及原工程路径。大电影仍不放入普通Git历史。

## 每次完成作品后

1. 完成原有技术检查，保留人工/真机待验收状态。把新作的 `delivery.json`、源码、素材及 QA 一起归档，不能只上传视频。
2. 在仓库根运行 `python3 scripts/build-archive-catalog.py`，检查作品/平台归类、源文件哈希和待上传集合。生成的历史索引不改动原始媒体；新作全部已声明目标必须达到 `delivery.json.duration_seconds` 中同一个 `T`（缺省 120 秒）及对应帧数，不能在归档时另套固定时长。新作默认声明 `platforms: ["xiaohongshu"]` 并保留对应完整验收，只归档已声明平台。历史作品继续保留原平台及全部正式版本，不能因默认值变化筛掉历史资产。
3. 用本技能的 `scripts/upload_releases.py --catalog <仓库>/archive/catalog.json --root <仓库>` 做只读本地预检。默认不联网上传；它会检查文件与清单是否匹配。
4. 检查变更范围，按本作品、技能及清单的具体路径提交；排除凭据、依赖、bundle、日志与无关并行修改。正常 push 到该仓库，不 force、不重写旧历史。确认远端含本次 commit。
5. 用相同 uploader 加 `--apply --target <已push的完整commit SHA>` 上传。先创建 draft Release，再逐文件上传并核对远端大小及 SHA-256 digest，全部通过后公开该 Release。不得在上传不完整时声称归档完成。
6. 如遇中断，修复实际原因后重跑同一清单；已验证相同内容会跳过。遇到同名但哈希不同的远端文件，保留旧文件并使用新作品版本/tag，不能 `--clobber`。
7. 交付时同时提供本地已声明平台的成片、GitHub commit、作品 Release 链接及远端核对结果。只有本地 commit、push、Release 上传全部成功，才说“已同步到 GitHub”。

## final 本地与GitHub双份留存

以下命令均从已核验远端为 `jggagi/video-making` 的仓库根目录执行。`scripts/build-final-library.py` 和 `scripts/fetch-archive-assets.py` 属于仓库脚本，不在安装的技能目录内；先确认这些文件存在。本机更新总目录后运行 `python3 scripts/build-final-library.py`。脚本从正式平台成片生成本地APFS克隆、`final/index.json`、`final/README.md` 和兼容现有上传器的 `final/backup-catalog.json`，排除样片、工程素材和ZIP。保留原路径和所有正式历史版本；目标内容不同则停止，不覆盖。APFS克隆与原件在同一块盘上，云端备份需要单独完成。其他机器遵守其当前存储规则，不照搬本机APFS操作。

先对final备份清单运行上传器默认dry-run。将源码、清单、索引提交并push后，执行：

```sh
python3 skills/xiaohongshu-video/scripts/upload_releases.py --catalog final/backup-catalog.json --root . --apply --target <已push完整commit-SHA> --receipt archive/upload-receipt-final-<完整commit-SHA>.json
```

为final使用单独receipt，避免与同commit的作品归档记录互相替代。每个 `final-*` Release仅含该作品正式平台视频；未来作品新增对应备份，已存在且匹配的资产直接跳过，上传失败可重跑，不删除或覆盖旧资产。

公开后逐项核对远端大小、SHA-256 digest与完整资产集合，保存 `final/backup-verification.json`，记录当前backup catalog散列、Release及资产身份。清单变化后，旧记录不能代表新增影片已经备份。只有本地final文件和当前云端final资产都匹配，才宣布双份留存完成。单独恢复final目录可运行 `python3 scripts/fetch-archive-assets.py --catalog final/backup-catalog.json --download`，下载器保留目录结构并验证散列。

每次新增final备份后，从本次新增成片中选择一份做真实恢复抽测：把仅含该文件的备份清单放进隔离临时目录，使用恢复器的 `--root <临时根目录> --catalog <抽测清单> --download` 下载，核对恢复后的相对路径、字节数与SHA-256；再执行一次，确认匹配文件被跳过。记录抽测文件身份、结果和范围并清理本次临时数据，不覆盖正式输出，也不把单份抽测表述为全部影片均已下载恢复。

用户以后调用本技能制作新片时，继续执行此同步约定。没有新作品产生时不创建后台任务、定时器或无关提交。上传失败时保留本地交付与可续传状态，明确报告实际剩余项。

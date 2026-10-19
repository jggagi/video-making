# EP06 科学依据与原稿校订

本片是基于真实研究的思想实验。`../source/script.md` 原样保留用户输入；`segments.json` 的 original_script、display_subtitle、tts_phonetic_text 分开保存。所有轨迹、遥测与百分比均为合成示意，无真人数据、脑电记录或预测能力实测。

## 01 准备电位不等于提前读心

[Libet et al. (1983), Brain](https://doi.org/10.1093/brain/106.3.623) 比较了简单自发动指任务中平均准备电位与回溯报告的主观意图时刻。采用常见的示意时间：RP≈−550ms、W≈−200ms、M=0，RP与W相隔约350ms。不能改说“意识前精确500ms知道念头”，也不能据此推出瞳孔/HRV可以读出下一句话，或SI能提前5秒完美预测人生。

[Schurger, Sitt & Dehaene (2012), PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC3479453/) 提出随机积累器解释平均RP；准备电位的解释与意识关系仍受讨论。画面中RP曲线是负电位向上的示意，不是实测，也不是一个确定的意图判别器。青色超前影子独立标为思想实验，不能当作脑电推断结果。

## 02 延迟嵌入不等于人格克隆

[Takens (1981), Detecting strange attractors in turbulence](https://link.springer.com/chapter/10.1007/BFb0091924) 针对光滑、有限维、满足一般性条件的动力系统与观测函数给出延迟嵌入结果。行为记录、人脑和完整人格不因这个定理就成为可重建且精确预测的系统。

本片实际积分Lorenz方程：dx/dt=10(y−x), dy/dt=x(28−z)−y, dz/dt=xy−(8/3)z；延迟坐标为(x(t),x(t−τ),x(t−2τ))。它是明确的合成演示。cyan/amber贴合为指定模拟收敛过程，HUD的0.001%是预设归一化轨迹误差，不能称为自由意志残差，也不声称测得99.999%人格预测准确率。混沌系统的延迟嵌入不消除有限精度、噪声和长期预测限制。

## 03 逆强化学习与塑形的边界

[Ng & Russell (2000), Algorithms for Inverse Reinforcement Learning](https://ai.stanford.edu/~ang/papers/icml00-irl.pdf) 从行为反推奖励函数；存在非唯一性和建模假设。不能等同于准确读出个人多巴胺奖赏函数。片中势场为手工定义的奖励景观，微扰改变路径成本，展示选择架构可能影响行为的直觉。不是对某个平台、个体或人一生的实测证明。

## 04 主权代理是边界设计，不是全能护盾

[Goldwasser, Micali & Rackoff (1989), The Knowledge Complexity of Interactive Proof Systems](https://epubs.siam.org/doi/10.1137/0218012) 的零知识证明支持在特定协议和假设下证明命题而不披露额外见证信息；不能阻止公网从其他数据推断偏好。

[Dwork & Roth (2014), The Algorithmic Foundations of Differential Privacy](https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf) 的ε-DP约束相邻数据库输出分布的概率比；不是“外部预测100%不确定”。Laplace机制尺度为Δf/ε，须有敏感度、隐私预算和组合会计。片中噪声通过Laplace逆CDF、Δf=1和ε=1生成固定种子可复现视觉纹理，未部署隐私系统、ZKP协议或真实量子/热随机源。随机性本身也不证明或恢复自由意志。

因此将“绝对物理隔离且对外通信”“唯一防线”“100% ENTROPY”“EXTERNAL PREDICTION BLOCKED”等绝对结论改为本地加密记忆、用户控制、最少披露的设计愿景。金色晶体的ACCESS DENIED表示拒绝访问本地保管库，不代表外部推断归零。输出不连接用户私人数据、无需真实密钥。

## 引句与时间调整

保留收官引句“把记忆锁进私密的圣殿……守住那百分之一的不可预测，才守住了生而为人的自由”，屏幕明确注明“百分之一”是诗意表达而非测量值。S08缩至90.5–95.667秒，旁白完整结束后留20帧全母带静音[5740,5760)，96秒锁库。S09移动至100.333–115.5秒，为原引句提供自然语速，不倍速、不截尾。

原稿的7±2与20W未作为本片定量推断依据。原始宣发文案保留在source，修订发布文案避免重复上述误导性断言。

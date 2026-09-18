# Q4 交付索引（问题四：波动电价下重算问题二与问题三）

> 生成：2026-09-13 02:02 ｜ 线别：对话 8（Q4）｜ 结构对齐 `Q1交付/` `Q2交付/` `Q3交付/`

## 一、交付物

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| `01_提交件/result4-2.xlsx` | 波动电价下问题二的完整购电策略（3 表） | ✅ 已完成（独立校验 11/11、errors=[]） |
| `01_提交件/result4-3.xlsx` | 波动电价下问题三的完整购电策略（4 表） | ✅ 已产出（待回填交付说明与终检） |

## 二、关键数字

| 口径 | 全年费用（元） | 说明 |
| --- | ---: | --- |
| Q2（附件1 价，非预见+因果裕度） | 13,252,341.09 | 继承基线（已冻结） |
| **Q4-2（附件4 价）** | **13,850,454.64** | 相对 Q2 **+4.51%** |
| Q3 v2（附件1 价，v2b 执行器） | **13,120,194.06** | 继承自 `Q3交付/`（旧 13,369,682.34 已作废） |
| **Q4-3（附件4 价，v2b）** | **13,727,033.66** | 相对 Q3 v2 **+4.63%**；闸门复现 Q3 v2 差 +0.00 |

**机制**：附件1 为附件4 的逐时段全年均值；波动电价抬高成本源于"价格日级水平与净负荷正相关（corr 0.9824）"，
2×2 反事实把它拆为**价格环境效应 +744,522.48** 与**重优化效应 −146,408.94**（净 +598,113.55）。

## 三、目录

| 目录 | 内容 |
| --- | --- |
| `01_提交件/` | 两份 result 文件 |
| `02_交付说明与附录/` | Q4-2 交付说明、Q4-3 模板与占位、监理整改说明、稳健性清单、防陷阱策略、继承规格、出题人视角 |
| `03_论文素材/` | 稳健性与封存清单、三方共验裁定（交付件/前沿） |
| `04_证据/` | 锚点、闸门、checkpoint、两部校验器结果、2×2、分块拆解、段数、裕度、λ、价格口径、指纹、全局陷阱雷达、三份监理报告 |
| `05_代码/` | 主线/物化/校验/Q4-3 驱动/反事实/指纹/扫描等脚本快照 |
| `06_图件/` | **由队长落地**（对话 8 只提供图件数据源清单，见 `Q4_最终产物清单与交接.md` §六） |

## 四、待补（不影响两份提交件成立）

1. `02_交付说明与附录/交付说明_Q4-3.md` —— 待回填（Q3 v2 哈希 `39F4C8DF…` + 全部关键数字 + 读法 C 声明）；
2. `03_论文素材/` —— 2×2 表、分块拆解表、机制段、17.9% 参数推导、D/U 两读法并列；
3. `06_图件/` —— 5 张图（SVG+300dpi PNG+manifest）；
4. Q4-3 的独立复算报告（现场监理 `q4_site_guard` 在跑）。

## 五、清单

| 文件 | 字节 | sha256 |
| --- | ---: | --- |
| `00_README_交付索引.md` | 9281 | `436531e1e5149de079879376bbcb5ed0a110302fcb41f5ae84cc2e2ed2ddbe42` |
| `01_提交件/result4-2.xlsx` | 426047 | `4f63fd2833bc4c55bf04badd04af3d6b8b09f7fbfbb6a18ca4927c1a53719455` |
| `01_提交件/result4-3.xlsx` | 850446 | `4f3e5f3fdd68563d8c533559ca952d7bf068aa5362de5283032379aa498cde4a` |
| `02_交付说明与附录/Q4-3_继承规格与执行器结论更正.md` | 11643 | `4af3ea261e12197cd84d9931329a8a695695c29f7b772615bc42bb0a334739ee` |
| `02_交付说明与附录/交付说明_Q4-2_波动电价完整购电策略.md` | 6095 | `8ca9cdc58fea1af93078304d9d588bc07a4e67cfddf63e8dcc7451586b53d656` |
| `02_交付说明与附录/交付说明_Q4-3.md` | 5128 | `03eab5c97fcb87ca02960ae709c914cee15978c04300c0ff1c6e775d46228a22` |
| `02_交付说明与附录/交付说明_Q4-3_待大队长签发.md` | 5128 | `03eab5c97fcb87ca02960ae709c914cee15978c04300c0ff1c6e775d46228a22` |
| `02_交付说明与附录/交付说明_Q4-3_未回填.md` | 282 | `2a41f0110f316dfc725be4ddbb718c32ebf01240c81a5df42ef39438ef33c100` |
| `02_交付说明与附录/交付说明模板_Q4-3.md` | 4095 | `ea29fef332141ed387d181d8ad7429d3d943e8c10b4dc4e03746e426bd3b91ad` |
| `02_交付说明与附录/出题人视角_反AI意图与评分识别点.md` | 9211 | `75ae84baf5e30b162be27456312b801e2730649bb34e922e0b60971cc0adf9b6` |
| `02_交付说明与附录/状态更新_交付前核对.md` | 3839 | `663e1361da6c8076fa33ab9aa470a97b324c77f2dd74af35c9096a02047cf79c` |
| `02_交付说明与附录/监理回执整改说明_Q4.md` | 3915 | `965a8f9a004c86fc220081e753822e0a917ef48067c755b5087b3da03256ca31` |
| `02_交付说明与附录/稳健性与封存清单_Q4.md` | 5118 | `17f3f745c0887dc27843b9089fd6ee708296ed2f9817005333b68d45d7ed5909` |
| `02_交付说明与附录/防陷阱策略_Q4.md` | 6818 | `50482d53271a81300120d34e4ca6eb965aa9fee5d5583c0290bcb7b8dcd66984` |
| `03_论文素材/Q4_稳健性与裕度结论.md` | 5118 | `17f3f745c0887dc27843b9089fd6ee708296ed2f9817005333b68d45d7ed5909` |
| `03_论文素材/三方共验_Q4交付件_裁定.md` | 7990 | `f46d1ddb635755a5f6ed7f31ad10b4244529fd34b03825613915f7074f9b9c77` |
| `03_论文素材/三方共验_Q4前沿与结构性遗漏_裁定.md` | 12301 | `1f5601710b8fc58a08873d50bd36df164804e776d19588b8334a3ac11e5941ee` |
| `04_证据/global_trap_scan.json` | 23515 | `6c4eea959bef38f9d860aa5d15e2749c62d396b5e2e7b037372f80f65092bc17` |
| `04_证据/q4_counterfactual_2x2.json` | 598 | `d7eedeed53a79a1bc4098c2780b6b749dd842d2b9fabf896b0fc2dc8c54cdaec` |
| `04_证据/q4_cp2_checkpoint.json` | 2393711 | `d84da2b04efa4783e7cdd31fd6d36c416b59c761657cdfca7eba1d6f30ee63fa` |
| `04_证据/q4_cp2_gate.json` | 3621 | `e82d4f55eedce912eaa5f4bdc6778c433bf4cac75a56d6dfec237a56350dc10e` |
| `04_证据/q4_cross_consistency_report.md` | 15282 | `ffd1e5e5f2439ca38221bef932525970475acc1117807a71e4ca06b4f2680703` |
| `04_证据/q4_data_anchor.json` | 2722 | `ff6107be280b6ae750135f69f7d38a93484df724a65c83111717d076359f2d99` |
| `04_证据/q4_design_guard_report.md` | 20404 | `d85d5275fa0aa2d8f1769a7f33949e3efd02d1eb4d0c99209df27b7912c78d44` |
| `04_证据/q4_gate_segments.json` | 195 | `2399da0820d06d6ee26e81335c5b4ae5d50298152dde452b32c71d2fae70aac3` |
| `04_证据/q4_leakage_injection.json` | 1117 | `eda0b1be476575c8c8561ff17b93226ba3952ff27d31ae015a26d78ff7501fa8` |
| `04_证据/q4_margin_M2_scan.json` | 1394 | `095b1501250dd210aaf2b451fa7a25ab0233d9fcf5a132286f6f3c25bc2bf040` |
| `04_证据/q4_margin_deepdive.json` | 567 | `12200dbce53b1ed7711e6cf3bf40f370a375a04fa24121a50b9c5f3b35328c81` |
| `04_证据/q4_price_block_decomp.json` | 680 | `83cc56e57540f1d1ea34dfbea502bcada4800df0befe0db39326f1f5e03159e6` |
| `04_证据/q4_probe_lambda_joint.json` | 1814 | `24eb57d17d26762ee912df5b1fc81ddf2344a56b6df4578d31d1657f2a75140d` |
| `04_证据/q4_probe_price_caliber_v2.json` | 849 | `e40216037cdfb3d80603edbfcb9a2c3de5fb03a84a382fa0f9c11ed815f1b578` |
| `04_证据/q4_q3v2_gate.json` | 617 | `7ea48582be42194ff0421dbd0f1fc8fcfbed53a4f87271e4383ec4238b06278e` |
| `04_证据/q4_q3v2_solution.json` | 2427796 | `6301417bd4a26408dd7588128be294adcc0f4c59649b822c9fc6b5604a33b1c4` |
| `04_证据/q4_q43_2x2.json` | 963 | `a8e72542f44c806218b8cfba8f172793ee29ee2c9e70c9b5568c7f0723c3dea5` |
| `04_证据/q4_q43_qm_scan.json` | 840 | `cb15d599885170e4a739bd47eb5c4d3e530f4cd71333fb264579a155c6593dcf` |
| `04_证据/q4_quality_guard_report.md` | 12913 | `c482b53950e993d884c338f6d90aacbd3c55dca7f3dcfdfd8a4e6624d026d43f` |
| `04_证据/q4_site_guard_report.md` | 16119 | `d62fd85063e59c140158deaea1b60ce1f8045bb857b42493a6da015aedbf5951` |
| `04_证据/q4_validator_result.json` | 6760 | `b5389ff1e65a84c22b5f3ea69ec2bfd41642a69f07491cf460529de83c72b52b` |
| `04_证据/q4_validator_result4-3.json` | 3784 | `3abaa33b24037278b54a55d7c9d803de5ba6beed191cfe2807b153af02410a71` |
| `04_证据/q4_validator_review_report.md` | 23028 | `75d0f81d7ae4d6df724d8dc474922d71c1e185284b783e42f95ff65284d655ea` |
| `04_证据/q4_verify_soc.json` | 2514 | `38983bff4d5b7ded42d123f7f34731a1e07b4f22a171e3c382fa35aaa2f65876` |
| `04_证据/site_guard_fingerprint.json` | 52987 | `343a93f5ebf59b4a1e8effda57125357e57e7496d0ee3bf7375f8cbbb2a3bcb5` |
| `05_代码/build_Q4_delivery.py` | 8038 | `cf56bfa339749f8580ef5cbb8d8e36d40d9235cc5105aae3a7f00e068474484b` |
| `05_代码/fix_result4_3_fee.py` | 2933 | `0107562063878182b0d0a648f301a557a1f5defa7f3833beba7ea4fbab1baead` |
| `05_代码/global_trap_scan.py` | 5928 | `b094c1951c5c123e6e0a4fe81bc5673e0e00855cac899d3cbe2e78536742b1de` |
| `05_代码/q4_counterfactual_2x2.py` | 5160 | `21865d12af2919c9fb8ee5397c3bcaf6b0aab85a5a6c988e69feed699fd3c650` |
| `05_代码/q4_data_io.py` | 5988 | `dae72568c32b382b49d49d1f1a14bf356d437f488b67cba3f2fc561980ca5245` |
| `05_代码/q4_det_seq.py` | 21036 | `30d3eee3ce255a858c3b583ba0d4a1c9573b00f0e6a2da18594b949abab22149` |
| `05_代码/q4_materialize.py` | 7594 | `e4b5e5ed1122a0ab921734b3ca8bce7252e03a26167a31d5adfe94569980ccfa` |
| `05_代码/q4_price_block_decomp.py` | 4643 | `adea22e04caa88505682a99e2ce22b3b169155f1d70d565374a8739adeb12680` |
| `05_代码/q4_q3v2_driver.py` | 4216 | `723463ceecfe572d8ba493f95bd8984555677c4938e8e251944ba72b0f678dfd` |
| `05_代码/q4_q43_2x2_and_pricearm.py` | 4397 | `aa6831db81095a974e6837dbd23d3efd880ce65d2268b6c415d92650af9cbf4e` |
| `05_代码/q4_q43_qm_scan.py` | 2873 | `b34eb3aa004ce94fe1da05d149649f750b57dc90a371ea61200019cc717c4181` |
| `05_代码/q4_validator.py` | 26731 | `7176722c40fba4c7276669315f2ce9e5aa09b3f65c085d76e1ebd0421c488bf6` |
| `05_代码/q4_validator_q3struct.py` | 11256 | `18d94e379789d9cd69bde34404e19f993b2c0fd287dfd8b8d4753d427fe4d8e3` |
| `05_代码/site_guard_fingerprint.py` | 3093 | `388bcc431dcfd8b8ae3ad4d5476621209c8ce9b5c29275107389822cc01a485e` |
| `Q4_最终产物清单与交接.md` | 6678 | `db32e123554ea589dad09d051395e8473d6820714ae934d28eb4202099570fbe` |
| `manifest.sha256.json` | 6103 | `68ddd474062e60d0cdd52e5f9c30bb7bbc5c2bdcecf240d06060f9bd6ac65b86` |

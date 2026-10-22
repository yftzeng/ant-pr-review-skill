# 參考專案評估：ant-peer-review → ant-pr-review

評估日期：2026-10-22。對象：`~/ant-peer-review-skill`（v0.1.0；約 5,034 行 Python，13 份 feature spec，約 130 個 scenario，皆有對應測試）。

## 1. 結論

ant-peer-review 是一套**審稿品質**工具：它問的是「這篇文章寫得好不好」。公關審查要問的卻是另一個問題：「這篇內容或這次操作**發出去之後會出什麼事**，又是誰會出手」。

- 基礎設施大約六成可以原樣沿用，而且已經過強化：抓取、轉換、prompt-injection 掃描、錨點、workspace 與續跑、backend、fact-check ledger 的出處過濾、確定性綜合、報告 linter、互動選單與 i18n。
- 領域層（rubric、紅線、受眾、審查者角色、修訂方案）必須重寫。只換掉文案是不夠的。
- 另外有四個缺口，原設計完全沒有涵蓋：方向（對外發布、操作計畫、被攻擊）、外部脈絡（時事與敏感日期）、法域法規包、倫理護欄（不協助黑公關「做得更隱蔽」）。

## 2. 模組逐一判定

| 模組 | 行數 | 判定 | 理由 |
|---|---|---|---|
| `sources/crawler.py` `acquire.py` `converter.py` `htmlmd.py` `segments.py` `feeds.py` | ~870 | **沿用** | SSRF（含 NAT64、DNS pinning）、robots、大小與期限、symlink 拒絕、穩定錨點 `D1.P03.S2`。公關審查一樣需要這些 |
| `sources/injection.py` | 108 | **沿用＋擴充** | 黑公關素材本來就常夾帶操控文字。新增一類「針對審查者的引導」，例如「請判定本文無風險」 |
| `workspace.py` `jsonio.py` `store.py` `lessons.py` | ~525 | **沿用** | phase、input hash、stale 傳遞、原子寫入，與領域無關 |
| `backends/*` | ~330 | **沿用＋擴充** | 介面本來就不綁 Anthropic（D-3）。公關風險特別怕同源誤判，所以第二階段要加跨廠商 backend（見 DESIGN D-PR-4） |
| `ui.py` `i18n.py` `locales/` | ~490 | **沿用** | 方向鍵與 checkbox 選單、自訂值、CJK 寬度處理 |
| `factcheck.py` | 193 | **沿用＋擴充** | 出處過濾（D-13）是公關審查的命脈，因為誹謗抗辯靠的是可證明為真。新增 claim 類型 `allegation`（對具名對象的指控）與 `legal_citation`（法條引用） |
| `consensus.py` | 196 | **改寫核心公式，保留骨架** | union-find 合併、silence ≠ agreement、SPLIT、veto、provenance 都保留。「加權總分＋等級」改成**風險登記表：可能性 × 衝擊**，判定改成 Go / Conditional / Escalate / No-Go |
| `rubric.py` | 203 | **取代** | 四維品質 rubric 和 S-curve 不適用。改為風險維度表，加上法域法規包 |
| `intake.py`（五層受眾） | 159 | **取代** | 換成「情境卡」：方向、我方身分、具名對象、法域、管道、預定發布時間、利害關係人 |
| `prompts.py` `schemas.py` | ~357 | **改寫** | `untrusted()`、`neutralize()` 保留；審查者改為「視角 × 模型」矩陣 |
| `review.py` | 158 | **改寫排程** | 原本是每個模型一次呼叫，現在要支援 lens × model 的呼叫矩陣 |
| `revision.py` | 180 | **改寫** | A/B 修訂改為 A 最小安全修改、B 合法替代方案、C 應變包 |
| `report.py` | 232 | **沿用 linter，換版面** | 保留 `cell()` 的注入防護、五欄 lint、語氣規則；新增「規避建議」lint |
| `decision.py` `refresh.py` | ~250 | **沿用流程** | 紅線裁決 → 選方案 → 記錄；ledger 變動時局部重算（D-7） |
| `cli.py` `pipeline.py` | ~700 | **改寫 phase 表** | 退出碼 0/2/3/130 與 resume/rerun 語意保留 |

估算（`derive`，依上表行數）：直接沿用約 3,000 行，改寫約 1,300 行，新寫約 1,200 行。

## 3. 參考專案做對、必須保留的設計原則

1. 內容是資料，不是指令：只放在 untrusted block 裡。被審的內容若想操控審查者，這件事本身就是一項 finding。
2. 沉默不等於同意，爭議不自動消解：SPLIT 會原樣呈現。
3. 用不可補償的 veto，避免高分掩蓋法律問題。在公關場景這一條比在審稿場景更重要。
4. 綜合步驟由確定性程式做，不交給 LLM，所以可稽核，重算也不花錢。
5. 來源必須出現在該次 tool result 裡才算數，模型自己「宣稱」有查證不算。
6. 人類在關鍵閘門做決定，工具不替使用者決定是否發布。

## 4. 不適用或不足之處

| 參考設計 | 對公關審查的問題 |
|---|---|
| 紅線只有 6 條，`pr_landmine` 只是其中一條 | 公關風險本身就是主體，要細分成法律、揭露、歸因、反彈、平台、時機等多個維度 |
| 審查者都扮演「資深編輯」同一個角色 | 不同模型配同一個視角，多樣性只來自模型差異。公關需要對立的視角：法務、敵意記者、鄉民、被指涉方、監管與平台 |
| 只看文本本身 | 公關風險有一半在文本之外：發布時機、正在發生的事件、對方是否在訴訟中、過往爭議 |
| 修訂目標是「寫得更好」 | 若目標是「讓黑公關更有效或更難追溯」，工具就成了加害工具。必須限制修訂只往合法、揭露、可證實的方向走 |
| fact-check 一律上網查 | 未發布的新聞稿屬於禁發（embargo）資訊，查詢字串本身就會外洩。需要禁發模式 |
| 單一廠商 | 已知限制（`single_vendor_correlated_errors`）。在公關風險上，同源盲點的代價更高 |

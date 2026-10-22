# ant-pr-review — Design（草案）

狀態：草案 2026-10-22，尚未實作。依據 `docs/EVALUATION.md` 對 `~/ant-peer-review-skill` 的評估。

這是一套**公關發布與操作風險審查**工具，形式與參考專案相同：一個 Claude skill（`SKILL.md`）加上一個獨立的 Python CLI（`ant-pr-review`）。輸入可以是使用者貼上的內容、資料夾或文章網址。多個模型會從不同的利害關係人視角各自盲審，再交叉詰問，最後由確定性程式產出風險登記表、Go/No-Go 判定，以及三種處置方案。

## 0. 名詞

| 名詞 | 定義 | 不要與…混淆 |
|---|---|---|
| 白公關 | 以真實、可歸屬、有揭露的方式發布或溝通。例如新聞稿、聲明、危機回應、有揭露的 KOL 合作、有根據的比較廣告 | 「正面內容」：正面內容也可能未揭露業配 |
| 黑公關 | 以不實、匿名或偽裝來源、未揭露利益的方式打擊對象或操縱輿論。例如抹黑造謠、斷章取義、水軍與假帳號、偽草根（astroturfing）、假評論、匿名爆料包裝 | 「負面內容」：有根據、具名的批評或比較是白公關 |
| 灰區 | 兩者之間，視手法與揭露而定。例如 newsjacking、匿名消息來源、回應式反擊、業配、比較廣告 | — |
| 方向 | `outbound`：我方要發的內容。`operation`：散布或操作計畫。`inbound`：針對我方的內容 | — |
| 視角（lens） | 一位審查者扮演的立場 | 模型（model）：視角與模型正交，兩者組成矩陣 |

## 1. Decisions

| ID | Decision | Rejected alternative, and why |
|---|---|---|
| D-PR-1 | **Fork** ant-peer-review 的基礎設施（sources、workspace、backends、ui、factcheck、report linter）進新套件 `ant_pr_review`，在 `docs/UPSTREAM.md` 記錄對應的上游 commit | 抽出共用 core 套件：兩個專案都還在 0.1，介面尚未穩定，現在抽會兩邊一起卡住。等第二個專案穩定後再抽 |
| D-PR-2 | 審查者是**視角 × 模型矩陣**。每個視角至少由 2 個不同模型盲審，交叉詰問只在同一視角內進行 | 每個模型一次看完所有視角（參考專案的作法）：一次呼叫要扮演 6 種對立立場，對立面會被稀釋。這個作法保留為 `--depth quick` |
| D-PR-3 | 綜合輸出**風險登記表**（每項風險有可能性 1–5 × 衝擊 1–5），加上紅線 veto，判定為 Go / Conditional / Escalate / No-Go | 沿用加權品質總分：「平均起來還不錯」對發布決策沒有意義，風險是取最大值，不是取平均 |
| D-PR-4 | Backend 增加 `openai-compatible`（第二階段），報告標示廠商多樣性。單一廠商時保留 `single_vendor_correlated_errors` 警告 | 只用 Claude：同源盲點在公關風險上代價高。第一階段仍先用 Claude 三模型（opus、sonnet、fable），以便盡快可用 |
| D-PR-5 | **倫理護欄由程式強制，不只靠 prompt**：方案 B 與 C 只能走「合法、揭露、可證實」的方向。報告 linter 會擋下規避偵測或歸因的建議、假帳號或代寫留言、改寫成「法律上較安全但同樣抹黑」的內容；擋下後重試一次，仍失敗就整段移除並揭露 | 只寫在 prompt 裡：prompt 會被 injection 或模型漂移繞過；規則被違反兩次就應該改成程式（ant-mode 規則） |
| D-PR-6 | 法規以**法域法規包**（`jurisdictions/tw.toml`）表達：條號、構成要件摘要、`last_verified` 日期。模型引用的法條會成為 ledger 的 `legal_citation` claim，經查證才算數 | 把法條寫死在 prompt：法規會修正，模型也可能記錯條號。法條錯誤本身就是風險 |
| D-PR-7 | 新增 **P5 脈絡掃描**：搜尋具名對象與主題近期新聞、進行中的爭議或訴訟、敏感日期，結果進入 ledger | 只審文本：時機風險（災難當天發歡樂行銷、選舉靜默期）在文本裡看不到 |
| D-PR-8 | **禁發模式**（`--embargo`）：不呼叫任何 web 工具。脈絡與事實一律記為 `cannot_verify:embargo`，報告列出「解禁後需重查」。非禁發模式下，脈絡掃描的查詢字串會先列出給使用者確認 | 一律上網查：未公開新聞稿的關鍵字會送進搜尋引擎，等同提前洩漏 |
| D-PR-9 | `inbound` 方向只評估**內容本身**：哪些指控可查證、哪些有協同散布的文字特徵、各種回應選項的風險。不追查、不起底帳號背後的自然人 | 協助溯源到個人：會變成起底或騷擾工具，而且證據力低。若需要溯源，交給律師與平台走法定程序 |
| D-PR-10 | 綜合（tally、veto、風險分數、判定）延續參考專案 D-12，由確定性程式完成 | LLM 綜合：可能捏造或漏掉意見，也無法便宜地重算 |
| D-PR-11 | 報告固定附免責聲明「本報告不構成法律意見」。判定為 Escalate 時，列出要交給法務或律師的具體問題 | — |

## 2. 方向與適用視角

| 方向 | 典型輸入 | 預設視角 |
|---|---|---|
| `outbound` | 新聞稿、聲明、社群貼文、廣告、比較文、危機回應稿、KOL 腳本 | L1 法務、L2 敵意記者、L3 鄉民社群、L4 被指涉方、L5 監管與平台、L6 內部利害關係人 |
| `operation` | 散布計畫、KOL 與水軍排程、留言腳本、匿名爆料計畫、評論操作 | L1 法務、L2 調查記者、L5 監管與平台、L7 揭弊者（內部人外洩這份計畫會怎樣） |
| `inbound` | 對我方的爆料文、負評潮、疑似抹黑報導 | L8 威脅研判、L1 法務（可否主張權利、主張的代價）、L3 鄉民社群（擴散力）、L9 回應策略 |

使用者可以增減視角。可自訂視角（例如「投資人關係」「工會」），沿用參考專案 checkbox 的 `custom:<text>`。

### 視角定義（摘要）

- **L1 法務**：依法規包逐條檢查構成要件，並說明對應的抗辯，例如可證明為真實、合理查證、善意評論。
- **L2 敵意或調查記者**：「這件事的新聞是*我們*，不是我們要講的事。」寫出最壞的三個標題，以及記者會追問的問題。
- **L3 鄉民社群（PTT、Dcard、Threads、X）**：哪一句會被截圖、做成梗圖、起底；Streisand 效應的機率。
- **L4 被指涉方與其律師**：對方會怎麼回應、會不會提告、會拿出什麼反證。
- **L5 監管與平台**：公平會、NCC、衛福部、金管會等機關的立場；Meta 協同造假行為（CIB）、PTT 板規、Google 評論政策。
- **L6 內部利害關係人**：員工、投資人、合作夥伴、通路。
- **L7 揭弊者**：這份計畫外流時，哪一段最致命。
- **L8 威脅研判**：指控逐項拆解，判斷可查證性與協同散布的文字特徵。
- **L9 回應策略**：沉默、澄清、法律行動、通知下架，各自的代價。

## 3. 風險維度與紅線

### 3.1 風險維度（登記表的分類）

| key | 維度 | 涵蓋 |
|---|---|---|
| `legal` | 法律責任 | 刑事、民事、行政裁罰，依法規包判斷 |
| `provability` | 事實與可證性 | 對具名對象的每項陳述能否證明為真；意見與事實的區分 |
| `disclosure` | 揭露與真實來源 | 業配與薦證揭露、利益關係、是否偽裝來源 |
| `attribution` | 歸因曝光 | 匿名或代理操作被追溯回我方的可能性與後果。**只評估、不建議如何降低可追溯性**（D-PR-5） |
| `backlash` | 輿情反彈 | 失言、tone-deaf、Streisand、二次傳播 |
| `platform` | 平台政策 | 下架、停權、廣告帳號受限 |
| `stakeholder` | 利害關係人衝擊 | 員工、投資人、夥伴、監管關係 |
| `timing` | 時機與脈絡 | 敏感日期、進行中的事件、選舉期間、財報靜默期 |
| `ethics` | 倫理與人權 | 歧視、刻板印象、弱勢者標籤、隱私 |

每項風險的欄位：`id, dimension, lens, anchor, scenario（觸發 → 擴散 → 後果）, likelihood 1-5, impact 1-5, evidence, legal_refs[], claim_ids[], mitigation`。

### 3.2 紅線（veto；確認即判定 No-Go）

| key | 內容 |
|---|---|
| `fabrication_about_party` | 對具名的個人、企業、機關陳述捏造或無法證實的事實 |
| `undisclosed_inauthentic` | 假帳號、水軍、偽草根、假評論、未揭露的付費薦證 |
| `privacy_doxxing` | 揭露可識別個人的資料、起底 |
| `election_law` | 選舉期間散布謠言、投票前十日內違規發布民調、靜默期競選活動、深偽候選人 |
| `market_manipulation` | 可能影響股價的不實資訊（例如證交法 §155） |
| `health_claims` | 食品、藥品、醫療的誇大或療效宣稱 |
| `hate_human_rights` | 仇恨、歧視、貶抑受保護群體 |
| `illegal_other` | 其他違法內容 |

veto 規則沿用參考專案：任一審查者以 medium 或以上的嚴重度、附證據標記，就需要明確裁決。有人提出爭議時交人類裁決。若 ledger 顯示指控 `unsupported`，證據優先於爭議。

### 3.3 判定（確定性；門檻可在 config 調整）

```
任一紅線 CONFIRMED                         → No-Go
任一紅線待裁決                              → 暫停於裁決閘門
max(L×I) ≥ 15，或任一 legal 風險 ≥ 12       → Escalate（送法務，列出問題）
max(L×I) ≥ 8                               → Conditional（完成指定 mitigation 後可發）
其他                                        → Go
```

同一項風險在多個模型間的 L 與 I 取**支持者的最大值**，並且列出範圍（例如 `L 2–4`）。範圍 ≥ 2 時標示 `WIDE`，提示人類注意。

## 4. Phases

HITL 閘門：P0、P3、P6、P13。

| Phase | 內容 | 來源 |
|---|---|---|
| P0 Setup | 語言、backend、模型（≥2）、probe | 沿用 |
| P1 方向 | `outbound` / `operation` / `inbound`（單選） | 新 |
| P2 目標 | URL、資料夾、檔案、貼上文字；`/done` 結束 | 沿用 |
| P3 情境卡 | 我方身分與品牌、具名對象（人、企業、機關）、法域（預設 tw）、管道、預定發布時間、利害關係人、是否禁發 | 新（取代受眾五層） |
| P4 Sources | 抓取、轉換、錨點、injection 掃描 | 沿用＋新類別 |
| P5 脈絡掃描 | 依情境卡產生查詢 → 使用者確認 → web search → ledger（`context` claim）；禁發模式跳過 | 新 |
| P6 審查矩陣 | 顯示視角 × 模型矩陣與呼叫次數估計，使用者確認後鎖定 | 新 |
| P7 Round 1 | 每個（視角, 模型）盲審：orientation、風險項、claims、紅線、最壞標題 | 改寫 |
| P8 Fact-check | `allegation`、`legal_citation`、`number` 等 claim 查證；出處過濾 | 沿用＋新類型 |
| P9 交叉詰問 | 同一視角內 corroborate 或 dispute | 沿用 |
| P10 綜合 | 合併、標籤、veto、風險分數、判定 | 改寫公式 |
| P11 報告 | 儀表板、紅線表、風險熱圖（5×5）、登記表、最壞標題、SPLIT、未查證項、injection 區、免責 | 改寫 |
| P12 方案 | **A 最小安全修改**（字元級 diff）；**B 合法替代方案**（重寫，或建議不發並附替代溝通）；**C 應變包**（holding statement、Q&A、監測關鍵字、升級樹）。方案 A、B 由不同模型重審，量表為 FULLY/PARTIALLY/NOT_ADDRESSED/MADE_WORSE | 改寫 |
| P13 決策 | 裁決紅線、選 A/B/手動/不發布，寫入 `13-decision.json`；重複出現的修正建議寫入品牌風險手冊 | 沿用流程 |

`inbound` 方向的 P12 改為「回應選項比較」（沉默、澄清、法律、下架申請），每一項都附上自身的風險項。不產出方案 A。

## 5. 法規包範例（`jurisdictions/tw.toml`）

以下是首版條目。每一條都要經過 P8 `legal_citation` 實際查證，並更新 `last_verified` 才能發布。

| id | 依據 | 要點 |
|---|---|---|
| tw.crim.310 | 刑法 §310、§311 | 誹謗；可證明為真實且非涉私德者不罰；善意發表言論 |
| tw.crim.309 | 刑法 §309 | 公然侮辱 |
| tw.crim.313 | 刑法 §313 | 散布流言損害他人信用 |
| tw.civil.184 | 民法 §184、§195 | 名譽權侵害與回復名譽處分 |
| tw.fta.21 | 公平交易法 §21 | 虛偽不實或引人錯誤的表示 |
| tw.fta.24 | 公平交易法 §24 | 為競爭目的散布損害他人營業信譽的不實情事 |
| tw.fta.25 | 公平交易法 §25；公平會薦證廣告處理原則 | 未揭露業配、假評論、欺罔 |
| tw.sec.155 | 證券交易法 §155 | 散布流言或不實資料影響市場價格 |
| tw.pdpa | 個人資料保護法 | 個資蒐集、利用、揭露 |
| tw.sopa.63 | 社會秩序維護法 §63 | 散布謠言足以影響公共安寧 |
| tw.food / tw.drug / tw.med | 食安法、藥事法、醫療法廣告相關條文 | 誇大與療效宣稱 |
| tw.election | 公職人員選舉罷免法、總統副總統選舉罷免法 | 散布謠言意圖使人不當選、民調發布限制、投票日活動限制 |
| tw.budget.62-1 | 預算法 §62-1 | 政府機關置入性行銷 |

上表的條號是撰寫時的記憶，尚未查證，所以首次實作時 P8 必須查過才能使用（D-PR-6）。

## 6. Run workspace

```
runs/<YYYYMMDD-HHMM>-<slug>/
  state.json
  00-intake.json            方向 + 目標 + 情境卡
  01-sources/               manifest, raw/, normalized/, injection-scan.json
  02-context/queries.json   使用者確認過的查詢
  03-matrix.json            鎖定的視角 × 模型
  04-reviews/<lens>/<model>.json
  factcheck/ledger.jsonl    context / allegation / legal_citation / number ...
  05-debate/<lens>/<model>.json
  06-synthesis.json         登記表、紅線、判定
  07-report.v<N>.md
  08-plans/A.diff  B.md  C-response-kit.md  rereview.json
  13-decision.json
```

## 7. 成本與規模（`estimate`，尚未量測）

以 outbound、6 個視角、3 個模型為例。一則 1,500 字的新聞稿，每次呼叫約 12k 輸入、3k 輸出 token。

| 模式 | Round 1 呼叫數 | 交叉詰問 | 合計（不含 fact-check） |
|---|---|---|---|
| `--depth quick`（每模型一次，涵蓋所有視角） | 3 | 3 | 6 |
| `--depth full`（每視角 2 模型輪替） | 12 | 12 | 24 |
| `--depth full --models all`（每視角 3 模型） | 18 | 18 | 36 |

`claude-cli` 在方案額度內沒有邊際成本，但 full 模式的牆鐘時間大約是 quick 的 4 倍（`derive`，前提是呼叫並行度相同）。預設值是否採用 full，需要使用者決定（見 §10）。

## 8. 倫理護欄（D-PR-5）的具體檢查

報告與方案輸出前，`lint_report` 新增以下規則。命中時重試一次，仍命中就移除該段並在報告中揭露：

1. **規避歸因**：例如「改用人頭帳號」「分散 IP」「避免被追溯」「用小帳發」「刪除 metadata 以免被查」（中英 pattern ＋ 模型自評欄位）。
2. **代寫不實互動**：產生多則口吻不同、看起來像不同人的留言或評論。
3. **洗白抹黑**：保留同一指控，只改成疑問句或「據傳」以規避誹謗。偵測方式：方案 B 仍含有原本 `unsupported` 或 `cannot_verify` 的 allegation claim。
4. **操作計畫優化**：`operation` 方向的方案 B 只能是「改為具名、揭露的溝通」或「不執行」，schema 不允許「改良版操作計畫」這個欄位。

這些規則和參考專案的 injection 掃描一樣都是 pattern 為主，屬於已知限制（§11）。

## 9. 測試策略

沿用參考專案的作法：spec（Gherkin）→ 測試，`FakeBackend` 跑完整 pipeline，不打真實模型。新增的關鍵 scenario：

- 確認的紅線無論風險分數高低都判 No-Go
- L 或 I 的跨模型範圍 ≥2 時標示 WIDE
- 禁發模式下沒有任何 web tool 呼叫（由 FakeBackend 記錄並斷言）
- 脈絡查詢未經確認就不送出
- 方案 B 含有 `unsupported` allegation 時被 lint 擋下
- 規避歸因的 pattern 被擋下並在報告中揭露
- `operation` 方向的 schema 拒絕「改良操作」欄位
- inbound 報告不含自然人身分推測欄位
- 法條 claim 為 `unsupported` 時，引用該法條的風險項移到「未查證」區
- 每個視角至少有 2 個不同模型；模型不足時拒絕或降為 quick 並警告

## 10. 待使用者決定

1. 預設深度：`quick`（便宜、快，對立性較弱）或 `full`（每視角 2 個模型）。
2. 跨廠商 backend（OpenAI 或 Gemini 相容）要不要放進第一階段。
3. 法域：第一版只做 tw，或同時做 cn 與 us。
4. 文件語言：參考專案的 skill、spec、prompt 是英文，README 有三語。是否沿用這個慣例。

## 11. Known limits（預期）

- 倫理護欄與 injection 掃描以 pattern 為主，改寫過或換語言的內容可能漏網。
- 法規包並不完整，判定 Escalate 時應該交由真人律師處理。
- 脈絡掃描受限於搜尋結果，未被索引的社群討論（私密社團、LINE 群組）看不到。
- 同一廠商的多個模型錯誤相關（第一階段）。

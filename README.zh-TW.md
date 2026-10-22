# ant-pr-review

多模型、跨廠商的**公關風險審查**工具，由 Claude skill（`SKILL.md`）加上獨立的 Python CLI 組成。[English](README.md) · [简体中文](README.zh-CN.md)

可以審查三種內容：
- **對外發布**：我方要發的內容（新聞稿、聲明、貼文、廣告、KOL 腳本）
- **操作計畫**：散布或輿論操作計畫
- **被攻擊**：針對我方的內容（爆料、抹黑、負評潮）

每一種都會依法域（台灣、美國、歐盟、中國）分別評估白公關與黑公關的發布與操作風險。

- **每題都由每個模型作答的檢核清單**：41 題，分屬 9 個利害關係人視角：法務、敵意記者、網路社群、被指涉方、監管與平台、內部人、揭弊者、威脅研判、回應策略。未作答的題目視為缺口，不算通過。
- **跨廠商**：可用方向鍵勾選 Claude（opus / sonnet / fable，經 `claude -p`）、OpenAI、Gemini、Grok、OpenRouter。全部來自同一家時仍可執行，但會醒目提示，因為同一廠商的模型盲點相近。
- **一個法域一組呼叫**：每個法域由各自的呼叫審查，不會一次處理多國。勾選多國時，會有一個獨立的匯整模型比較各國結果、向各國審查者提問討論，再產出匯整版報告與各國版報告。
- **兩種深度**：`quick` 是每個模型一次，加上每個法域一次；`full` 是每個視角、每個法域各一次，呼叫數約為 quick 的 4 倍。
- **判定由程式計算**：風險登記表（可能性 × 衝擊）、紅線否決（對具名對象的捏造陳述、水軍與未揭露業配、起底、選舉法規、影響股價、療效宣稱、仇恨），最後給出可發布／有條件／送審／不可發布。
- **有倫理護欄的處置方案 A/B/C**：A 是最小安全修改（字元級 diff），B 是合法替代方案，C 是應變包。護欄會移除隱匿身分或規避追溯的建議、假冒網友的留言，以及只換說法的抹黑，並標示移除了什麼。
- **禁發模式**：未公開的內容完全不上網查詢。脈絡掃描的查詢字串會先列出，經你同意才送出。

本工具不構成法律意見。`src/ant_pr_review/jurisdictions/` 裡的法規包只是尚未查證的起點清單；模型引用的每一條法條都會經過事實查核。

## 安裝

```
uv tool install .        # 或 pipx install .
ant-pr-review            # 互動模式
```

JavaScript 渲染的網頁：`uv tool install '.[render]'`，再執行 `playwright install chromium`。抓取失敗時的順序是：退避重試 → 無頭瀏覽器 → AMP 版本 → 標註日期的 Wayback Machine 存檔 → 請你貼上內文。爬蟲不會偽裝成瀏覽器。

需要 Python 3.11 以上。使用 Claude 模型需要 `claude` CLI；使用其他廠商需設定對應的 key：`OPENAI_API_KEY`、`GEMINI_API_KEY`、`XAI_API_KEY`、`OPENROUTER_API_KEY`。沒有任何 runtime 相依套件。

## 非互動模式

```
ant-pr-review new --yes --direction outbound --jurisdictions tw,us --depth full \
  --party "競爭對手A" --embargo --target ./release.md
ant-pr-review decide <run> --yes --choice A
```

加上 `--backend fake` 可以離線試跑。設計見 `docs/DESIGN.md`；對 ant-peer-review 的評估見 `docs/EVALUATION.md`。

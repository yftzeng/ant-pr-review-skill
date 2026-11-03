"""Regional usage of Chinese text (ported from ant-peer-review's outlang).

A statement in Traditional Chinese for Taiwan that carries Simplified characters or
mainland terms (視頻, 信息, 軟件), or the reverse, tells readers where it was written
and is itself a PR risk. Checked, never changed: a statement is edited by people.
Quotes and URLs are skipped: quoting a source verbatim is fine. Political naming is
the sovereign red line's job, not this check's."""
from __future__ import annotations

import re

URL_RE = re.compile(r"https?://[^\s<>\"'，。、）」]+", re.I)

# Characters used only in one script (pairs: simplified, traditional).
_PAIRS = ("们們 这這 说說 时時 发發 为為 会會 对對 经經 过過 还還 进進 现現 实實 动動 开開 "
          "关關 门門 问問 间間 长長 东東 车車 书書 见見 话話 语語 读讀 写寫 认認 识識 让讓 "
          "应應 该該 网網 络絡 软軟 视視 频頻 数數 据據 质質 设設 计計 个個 国國 学學 样樣 "
          "业業 电電 与與 务務 级級 产產 无無 体體").split()
SIMPLIFIED_ONLY = "".join(p[0] for p in _PAIRS)
TRADITIONAL_ONLY = "".join(p[1] for p in _PAIRS)

# zh-TW: mainland term (in Traditional script) -> Taiwan term.
TW_SAFE = {
    "源代碼": "原始碼", "代碼": "程式碼", "程序員": "程式設計師", "軟件": "軟體", "硬件": "硬體",
    "視頻": "影片", "默認": "預設", "網絡": "網路", "服務器": "伺服器", "鼠標": "滑鼠",
    "打印": "列印", "博客": "部落格", "數據庫": "資料庫", "屏幕": "螢幕", "內存": "記憶體",
    "菜單": "選單", "文件夾": "資料夾", "芯片": "晶片", "操作系統": "作業系統",
    "互聯網": "網際網路", "數字化": "數位化", "智能": "智慧", "短信": "簡訊", "出租車": "計程車",
    "搜索": "搜尋", "鏈接": "連結", "模塊": "模組", "緩存": "快取", "異步": "非同步",
    "線程": "執行緒", "變量": "變數", "數組": "陣列", "字符串": "字串", "硬盤": "硬碟",
    "激活": "啟用",
}
TW_FLAG = {
    "項目": "專案", "質量": "品質", "信息": "資訊", "用戶": "使用者", "支持": "支援",
    "運行": "執行", "通過": "透過", "程序": "程式", "對象": "物件", "函數": "函式",
    "數據": "資料", "調用": "呼叫", "接口": "介面", "登錄": "登入",
}
# zh-CN: Taiwan term (in Simplified script) -> mainland term.
CN_SAFE = {
    "程式设计师": "程序员", "程式码": "代码", "原始码": "源代码", "软体": "软件", "硬体": "硬件",
    "伺服器": "服务器", "滑鼠": "鼠标", "列印": "打印", "部落格": "博客", "资料库": "数据库",
    "萤幕": "屏幕", "记忆体": "内存", "晶片": "芯片", "作业系统": "操作系统",
    "网际网路": "互联网", "网路": "网络", "简讯": "短信", "计程车": "出租车", "搜寻": "搜索",
    "模组": "模块", "快取": "缓存", "非同步": "异步", "执行绪": "线程", "变数": "变量",
    "阵列": "数组", "字串": "字符串", "硬碟": "硬盘",
}
CN_FLAG = {
    "专案": "项目", "资讯": "信息", "使用者": "用户", "影片": "视频", "预设": "默认",
    "物件": "对象", "程式": "程序", "透过": "通过", "品质": "质量",
}

_QUOTED = re.compile(r"「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"\n]*\"|《[^》]*》")

def _rules(lang: str):
    if lang == "zh-TW":
        return TW_SAFE, TW_FLAG, SIMPLIFIED_ONLY
    if lang == "zh-CN":
        return CN_SAFE, CN_FLAG, TRADITIONAL_ONLY
    return {}, {}, ""



def check(text: str, lang: str | None) -> list[dict]:
    """script_mismatch (characters of the other script) and locale_term (a term with one
    clear regional equivalent); English and terms with a local meaning too are left out."""
    safe, _, wrong = _rules(lang or "")
    if not wrong:
        return []
    view = URL_RE.sub(" ", _QUOTED.sub(" ", text))
    out = []
    script = "".join(dict.fromkeys(c for c in view if c in wrong))
    if script:
        out.append({"code": "script_mismatch", "detail": script[:10]})
    out += [{"code": "locale_term", "detail": f"{src} → {safe[src]}"}
            for src in sorted(safe, key=len, reverse=True) if src in view]
    return out

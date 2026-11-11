# 語音情緒辨識文獻筆記站

這是我自己複習語音情緒辨識（SER）論文用的筆記站，每篇論文一頁，欄位固定，首頁依年份分組。

線上網站連結：https://jacky1-collab.github.io/speech-emotion-notes/

## 專案與筆記說明

論文 PDF 只放在我本機的 `pdf/`，不放進 repo，repo 內只有我自己整理的筆記。

這個專案由 AI 協助新增筆記，規則都寫在 `AGENTS.md`；新增一篇筆記時，只要先把論文 PDF 放進 `pdf/`，再請 AI 先讀 `AGENTS.md`；AI 會先提出計畫，我確認後才會動手。

## 本機預覽方式

在專案最外層目錄執行以下指令啟動本機伺服器：

```bash
python -m http.server 8000
```

接著在瀏覽器中開啟 [http://localhost:8000](http://localhost:8000) 即可瀏覽首頁與筆記目錄。

> 注意：請勿直接以瀏覽器雙擊開啟 `index.html` 檔案，瀏覽器之安全限制會阻擋跨來源 `fetch` 載入目錄資料。

## 檢查規範

新增筆記或修改時，請執行檢查腳本以確保格式一致與路徑正確：

```bash
python scripts/check.py
```

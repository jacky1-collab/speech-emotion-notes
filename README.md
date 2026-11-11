# 語音情緒辨識文獻筆記站

本站為「語音情緒辨識」（Speech Emotion Recognition, SER）之論文閱讀筆記網站，採純靜態網頁架構（HTML、CSS、JavaScript），適合部署於 GitHub Pages。

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

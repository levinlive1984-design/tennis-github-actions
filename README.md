# Tennis BO3 Odds Filter

這個專案會每天自動抓 Pinnacle 網球 moneyline，篩選低賠方歐賠 1.70～1.80 的賽事，並發布成 GitHub Pages 靜態頁。

輸出網址格式：

```text
[https://<你的 GitHub 帳號>.github.io/<repo 名稱>/](https://levinlive1984-design.github.io/tennis-github-actions/)
[https://<你的 GitHub 帳號>.github.io/<repo 名稱>/today_matches.json](https://levinlive1984-design.github.io/tennis-github-actions/today_matches.json)
[https://<你的 GitHub 帳號>.github.io/<repo 名稱>/today_matches.txt](https://levinlive1984-design.github.io/tennis-github-actions/today_matches.txt)
```

## 檔案說明

- `tennis_filter.py`：抓取、篩選、輸出資料。
- `requirements.txt`：Python 依賴套件。
- `.github/workflows/update-tennis-pages.yml`：GitHub Actions 排程與 Pages 部署。
- `docs/`：GitHub Pages 靜態輸出資料夾。

## 手動執行

```bash
pip install -r requirements.txt
python tennis_filter.py
```

## GitHub Pages 設定

Repository → Settings → Pages → Source 選擇 `GitHub Actions`。

## GPT 專案觸發詞建議

「請提供今日已篩選」

然後 GPT 專案指令應要求讀取：

```text
https://<你的 GitHub 帳號>.github.io/<repo 名稱>/today_matches.json
```

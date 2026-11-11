#!/usr/bin/env python3
"""
scripts/check.py — 語音情緒辨識文獻筆記站檢查腳本

此腳本為唯讀檢查工具，不修改任何專案檔案。
依據 AGENTS.md 檢查：
1. data/notes.json 可解析、每項恰好四個欄位且型別正確、排序正確、path 不重複。
2. 每個 path 對應的檔案都存在。
3. 檔名符合 <年份>-<小寫英文與連字號>.html，且所在年份資料夾、檔名年份、year 欄位三者一致。
4. 每篇筆記的 paper-title、paper-year、paper-summary（解碼後文字）與 notes.json 一致。
5. 每篇筆記的六個 <h2> 標題和順序正確。
6. 筆記頁有 lang="zh-Hant"、viewport、<title>、回首頁連結。
7. 站內的 href / src 沒有以 / 開頭，沒有 localhost、127.0.0.1。
8. .gitignore 含 pdf/ 和 *.pdf；若在 Git 專案內，git ls-files 裡沒有任何 .pdf。
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path
from html.parser import HTMLParser

EXPECTED_HEADINGS = [
    "論文基本資料",
    "一句摘要",
    "研究問題",
    "資料集",
    "方法",
    "結果",
]

FILENAME_REGEX = re.compile(r"^(\d{4})-[a-z0-9]+(-[a-z0-9]+)*\.html$")


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}


class HtmlInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_lang = None
        self.has_viewport = False
        self.title_text = []
        self._in_title = False

        self.headings_h2 = []
        self._in_h2 = False
        self._current_h2_text = []

        self.captured_ids = {}  # id -> text
        self._target_stack = []  # stack of (tag, id, [text_fragments])

        self.has_home_link = False
        self.links = []  # list of (attr_name, attr_value)

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attrs_dict = {k.lower(): v for k, v in attrs}

        if tag_lower == "html":
            if "lang" in attrs_dict:
                self.html_lang = attrs_dict["lang"]

        if tag_lower == "meta":
            if attrs_dict.get("name", "").lower() == "viewport" and "content" in attrs_dict:
                self.has_viewport = True

        if tag_lower == "title":
            self._in_title = True

        if tag_lower == "h2":
            self._in_h2 = True
            self._current_h2_text = []

        # Check href / src
        for attr in ("href", "src"):
            if attr in attrs_dict and attrs_dict[attr] is not None:
                val = attrs_dict[attr]
                self.links.append((attr, val))
                if attr == "href" and val == "../../index.html":
                    self.has_home_link = True

        # Check target IDs: paper-title, paper-year, paper-summary
        elem_id = attrs_dict.get("id")
        if elem_id in ("paper-title", "paper-year", "paper-summary"):
            self._target_stack.append((tag_lower, elem_id, []))
        elif self._target_stack and tag_lower not in VOID_TAGS:
            # Nested non-void element inside target id element
            self._target_stack.append((tag_lower, None, None))

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._in_title = False

        if tag_lower == "h2":
            self._in_h2 = False
            self.headings_h2.append("".join(self._current_h2_text).strip())
            self._current_h2_text = []

        if self._target_stack:
            for idx in range(len(self._target_stack) - 1, -1, -1):
                if self._target_stack[idx][0] == tag_lower:
                    while len(self._target_stack) > idx:
                        popped_tag, elem_id, fragments = self._target_stack.pop()
                        if elem_id and fragments is not None:
                            self.captured_ids[elem_id] = "".join(fragments).strip()
                    break

    def handle_data(self, data):
        if self._in_title:
            self.title_text.append(data)
        if self._in_h2:
            self._current_h2_text.append(data)
        if self._target_stack:
            # Append data to the innermost target that collects text
            for item in reversed(self._target_stack):
                if item[1] is not None:
                    item[2].append(data)
                    break

    def get_title(self):
        return "".join(self.title_text).strip()


def check_notes_json(root: Path):
    """檢查 1: data/notes.json 可解析、每項恰好四個欄位且型別正確、排序正確、path 不重複。"""
    notes_file = root / "data" / "notes.json"
    errors = []

    if not notes_file.is_file():
        return False, ["data/notes.json 檔案不存在"], []

    try:
        content = notes_file.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as e:
        return False, [f"data/notes.json 解析 JSON 失敗: {e}"], []

    if not isinstance(data, list):
        return False, ["data/notes.json 根節點必須是陣列 (list)"], []

    required_keys = {"title", "year", "summary", "path"}
    paths_seen = set()

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"第 {idx+1} 筆資料不是物件 (dict)")
            continue

        item_keys = set(item.keys())
        if item_keys != required_keys:
            errors.append(f"第 {idx+1} 筆欄位不符，必須恰好四個欄位 {required_keys}，實際為 {item_keys}")

        # 型別檢查
        if "title" in item and not isinstance(item["title"], str):
            errors.append(f"第 {idx+1} 筆 'title' 型別錯誤，必須為字串 (str)")
        if "year" in item:
            # Python 中 bool 是 int 的子類別，需排除 bool
            if type(item["year"]) is not int:
                errors.append(f"第 {idx+1} 筆 'year' 型別錯誤，必須為整數 (int)")
        if "summary" in item and not isinstance(item["summary"], str):
            errors.append(f"第 {idx+1} 筆 'summary' 型別錯誤，必須為字串 (str)")
        if "path" in item:
            if not isinstance(item["path"], str):
                errors.append(f"第 {idx+1} 筆 'path' 型別錯誤，必須為字串 (str)")
            else:
                p = item["path"]
                if p in paths_seen:
                    errors.append(f"第 {idx+1} 筆 'path' 重複: {p}")
                paths_seen.add(p)

    # 排序檢查：年份新到舊（由大到小），同年依 path 字母順序
    if not errors and len(data) > 1:
        sorted_data = sorted(data, key=lambda x: (-x["year"], x["path"]))
        if data != sorted_data:
            errors.append("data/notes.json 排序不正確，應為年份新到舊，同年依 path 字母順序")

    return len(errors) == 0, errors, data


def check_paths_exist(root: Path, notes: list):
    """檢查 2: 每個 path 對應的檔案都存在。"""
    errors = []
    for item in notes:
        p = item.get("path")
        if not p or not isinstance(p, str):
            continue
        file_path = root / p
        if not file_path.is_file():
            errors.append(f"筆記檔案不存在: {p}")
    return len(errors) == 0, errors


def check_filename_and_year(notes: list):
    """檢查 3: 檔名符合 <年份>-<小寫英文與連字號>.html，且所在年份資料夾、檔名年份、year 欄位三者一致。"""
    errors = []
    for item in notes:
        p = item.get("path")
        year = item.get("year")
        if not p or not isinstance(p, str) or not isinstance(year, int):
            continue

        normalized_p = p.replace("\\", "/")
        parts = normalized_p.split("/")

        if len(parts) != 3 or parts[0] != "notes":
            errors.append(f"路徑格式不符合 notes/<年份>/<檔名>.html: {p}")
            continue

        folder_year_str, filename = parts[1], parts[2]
        match = FILENAME_REGEX.match(filename)
        if not match:
            errors.append(f"檔名不符合 '<年份>-<小寫英文與連字號>.html': {filename}")
            continue

        file_year_str = match.group(1)
        expected_year_str = str(year)

        if folder_year_str != expected_year_str:
            errors.append(f"年份資料夾 ({folder_year_str}) 與 notes.json 的 year ({expected_year_str}) 不一致: {p}")
        if file_year_str != expected_year_str:
            errors.append(f"檔名年份 ({file_year_str}) 與 notes.json 的 year ({expected_year_str}) 不一致: {p}")

    return len(errors) == 0, errors


def parse_html_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8")
    parser = HtmlInspector()
    parser.feed(content)
    return parser


def check_notes_html_content(root: Path, notes: list):
    """
    檢查 4: 每篇筆記的 paper-title、paper-year、paper-summary（解碼後文字）與 notes.json 一致。
    檢查 5: 每篇筆記的六個 <h2> 標題和順序正確。
    檢查 6: 筆記頁有 lang="zh-Hant"、viewport、<title>、回首頁連結。
    """
    errors_c4 = []
    errors_c5 = []
    errors_c6 = []

    for item in notes:
        p = item.get("path")
        if not p:
            continue
        file_path = root / p
        if not file_path.is_file():
            continue

        try:
            parser = parse_html_file(file_path)
        except Exception as e:
            errors_c4.append(f"解析 {p} HTML 失敗: {e}")
            continue

        # Check 4: paper-title, paper-year, paper-summary
        title_in_html = parser.captured_ids.get("paper-title")
        year_in_html = parser.captured_ids.get("paper-year")
        summary_in_html = parser.captured_ids.get("paper-summary")

        if title_in_html is None:
            errors_c4.append(f"[{p}] 缺少 id='paper-title' 元素")
        elif title_in_html != item.get("title"):
            errors_c4.append(f"[{p}] id='paper-title' 內容 ({repr(title_in_html)}) 與 notes.json ({repr(item.get('title'))}) 不一致")

        if year_in_html is None:
            errors_c4.append(f"[{p}] 缺少 id='paper-year' 元素")
        else:
            try:
                year_num = int(year_in_html)
                if year_num != item.get("year"):
                    errors_c4.append(f"[{p}] id='paper-year' ({year_num}) 與 notes.json ({item.get('year')}) 不一致")
            except ValueError:
                errors_c4.append(f"[{p}] id='paper-year' 非數字: {repr(year_in_html)}")

        if summary_in_html is None:
            errors_c4.append(f"[{p}] 缺少 id='paper-summary' 元素")
        elif summary_in_html != item.get("summary"):
            errors_c4.append(f"[{p}] id='paper-summary' 內容 ({repr(summary_in_html)}) 與 notes.json ({repr(item.get('summary'))}) 不一致")

        # Check 5: <h2> headings
        if parser.headings_h2 != EXPECTED_HEADINGS:
            errors_c5.append(f"[{p}] <h2> 標題與順序不正確。實際: {parser.headings_h2}，預期: {EXPECTED_HEADINGS}")

        # Check 6: lang="zh-Hant", viewport, <title>, back link
        if parser.html_lang != "zh-Hant":
            errors_c6.append(f"[{p}] <html> 標籤缺少 lang='zh-Hant' (實際為 {repr(parser.html_lang)})")
        if not parser.has_viewport:
            errors_c6.append(f"[{p}] 缺少 <meta name='viewport' ...>")
        if not parser.get_title():
            errors_c6.append(f"[{p}] 缺少 <title> 或內容為空")
        if not parser.has_home_link:
            errors_c6.append(f"[{p}] 缺少指向 ../../index.html 的回首頁連結")

    # 同時對 templates/note-template.html 執行 Check 5 與 Check 6 規範驗證
    template_path = root / "templates" / "note-template.html"
    if template_path.is_file():
        try:
            t_parser = parse_html_file(template_path)
            if t_parser.headings_h2 != EXPECTED_HEADINGS:
                errors_c5.append(f"[templates/note-template.html] <h2> 標題與順序不正確。實際: {t_parser.headings_h2}")
            if t_parser.html_lang != "zh-Hant":
                errors_c6.append(f"[templates/note-template.html] <html> 標籤缺少 lang='zh-Hant'")
            if not t_parser.has_viewport:
                errors_c6.append("[templates/note-template.html] 缺少 viewport meta")
            if not t_parser.get_title():
                errors_c6.append("[templates/note-template.html] 缺少 <title>")
            if not t_parser.has_home_link:
                errors_c6.append("[templates/note-template.html] 缺少回首頁連結")
        except Exception as e:
            errors_c6.append(f"解析 templates/note-template.html 失敗: {e}")

    return (
        (len(errors_c4) == 0, errors_c4),
        (len(errors_c5) == 0, errors_c5),
        (len(errors_c6) == 0, errors_c6),
    )


def check_relative_links(root: Path):
    """檢查 7: 站內的 href / src 沒有以 / 開頭，沒有 localhost、127.0.0.1。"""
    errors = []
    # 掃描專案內所有 .html 檔案
    html_files = list(root.glob("*.html")) + list(root.glob("templates/**/*.html")) + list(root.glob("notes/**/*.html"))

    for html_file in html_files:
        rel_path = html_file.relative_to(root).as_posix()
        try:
            parser = parse_html_file(html_file)
        except Exception as e:
            errors.append(f"讀取 {rel_path} 失敗: {e}")
            continue

        for attr_name, val in parser.links:
            val_clean = val.strip()
            # 檢查 localhost 與 127.0.0.1
            if "localhost" in val_clean.lower() or "127.0.0.1" in val_clean:
                errors.append(f"[{rel_path}] {attr_name}='{val}' 包含 localhost 或 127.0.0.1")

            # 站內路徑不可由 / 或 \\ 開頭
            # 外部連結 (http://, https://, mailto:, etc.) 與錨點 (#) 除外
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", val_clean) or val_clean.startswith("#"):
                continue

            if val_clean.startswith("/") or val_clean.startswith("\\"):
                errors.append(f"[{rel_path}] 站內路徑 {attr_name}='{val}' 不得以 '/' 或 '\\' 開頭")

    return len(errors) == 0, errors


def check_gitignore_and_pdf(root: Path):
    """檢查 8: .gitignore 含 pdf/ 和 *.pdf；若在 Git 專案內，git ls-files 裡沒有任何 .pdf。"""
    errors = []
    gitignore_path = root / ".gitignore"

    if not gitignore_path.is_file():
        errors.append(".gitignore 檔案不存在")
    else:
        lines = [line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()]
        has_pdf_dir = any(line in ("pdf/", "/pdf/", "pdf/*") for line in lines)
        has_star_pdf = any(line in ("*.pdf", "*.PDF") for line in lines)

        if not has_pdf_dir:
            errors.append(".gitignore 必須包含 'pdf/'")
        if not has_star_pdf:
            errors.append(".gitignore 必須包含 '*.pdf'")

    # 若在 Git 專案內，檢查 git ls-files
    git_dir = root / ".git"
    if git_dir.is_dir():
        try:
            res = subprocess.run(
                ["git", "ls-files"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True
            )
            tracked_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
            tracked_pdfs = [f for f in tracked_files if f.lower().endswith(".pdf")]
            if tracked_pdfs:
                errors.append(f"Git 追蹤中發現 PDF 檔案（禁止提交 PDF）：{tracked_pdfs}")
        except Exception as e:
            errors.append(f"執行 git ls-files 檢查失敗: {e}")

    return len(errors) == 0, errors


def main():
    root = Path(__file__).resolve().parent.parent
    print(f"=== 語音情緒辨識文獻筆記站 規格檢查 ===")
    print(f"專案根目錄: {root}\n")

    all_passed = True

    # 1. data/notes.json
    ok1, err1, notes_data = check_notes_json(root)
    if ok1:
        print("[PASS] 檢查 1: data/notes.json 格式與排序正確（共收錄 %d 篇筆記）" % len(notes_data))
    else:
        all_passed = False
        print("[FAIL] 檢查 1: data/notes.json 格式不符合規範")
        for e in err1:
            print(f"       - {e}")

    # 2. Path 檔案存在
    ok2, err2 = check_paths_exist(root, notes_data)
    if ok2:
        print("[PASS] 檢查 2: notes.json 中所有 path 對應之筆記檔案皆存在")
    else:
        all_passed = False
        print("[FAIL] 檢查 2: 有筆記檔案遺失")
        for e in err2:
            print(f"       - {e}")

    # 3. 檔名與年份一致性
    ok3, err3 = check_filename_and_year(notes_data)
    if ok3:
        print("[PASS] 檢查 3: 檔名與資料夾年份規範一致")
    else:
        all_passed = False
        print("[FAIL] 檢查 3: 檔名或年份資料夾不一致")
        for e in err3:
            print(f"       - {e}")

    # 4, 5, 6. 筆記 HTML 內容與標籤檢查
    (ok4, err4), (ok5, err5), (ok6, err6) = check_notes_html_content(root, notes_data)

    if ok4:
        print("[PASS] 檢查 4: paper-title、paper-year、paper-summary 與 notes.json 一致")
    else:
        all_passed = False
        print("[FAIL] 檢查 4: 筆記內容欄位與 notes.json 不一致")
        for e in err4:
            print(f"       - {e}")

    if ok5:
        print("[PASS] 檢查 5: 筆記頁六個 <h2> 標題文字與順序完全正確")
    else:
        all_passed = False
        print("[FAIL] 檢查 5: 筆記頁 <h2> 標題或順序不符")
        for e in err5:
            print(f"       - {e}")

    if ok6:
        print("[PASS] 檢查 6: 筆記頁 lang='zh-Hant'、viewport、title、回首頁連結均正確")
    else:
        all_passed = False
        print("[FAIL] 檢查 6: 筆記頁缺少必要範本元素")
        for e in err6:
            print(f"       - {e}")

    # 7. 站內相對路徑與禁止項目
    ok7, err7 = check_relative_links(root)
    if ok7:
        print("[PASS] 檢查 7: 所有站內連結皆為合法相對路徑（無 '/' 開頭，無 localhost/127.0.0.1）")
    else:
        all_passed = False
        print("[FAIL] 檢查 7: 發現不合規定的路徑連結")
        for e in err7:
            print(f"       - {e}")

    # 8. .gitignore 與 PDF 追蹤
    ok8, err8 = check_gitignore_and_pdf(root)
    if ok8:
        git_note = "（Git 尚未初始化，已驗證 .gitignore 規則）" if not (root / ".git").is_dir() else "（已驗證 git ls-files 無 PDF）"
        print(f"[PASS] 檢查 8: .gitignore 規則正確 {git_note}")
    else:
        all_passed = False
        print("[FAIL] 檢查 8: .gitignore 規則或 Git 追蹤檔案檢查失敗")
        for e in err8:
            print(f"       - {e}")

    print("\n" + "=" * 45)
    if all_passed:
        print(">>> 全部檢查項目皆通過 (ALL PASSED) <<<")
        sys.exit(0)
    else:
        print(">>> 檢查未通過，請修正上述錯誤後重跑 (FAILED) <<<")
        sys.exit(1)


if __name__ == "__main__":
    main()

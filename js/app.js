// 語音情緒辨識文獻筆記站 — 首頁目錄載入程式

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('notes-list');
  if (!container) {
    return;
  }

  fetch('data/notes.json')
    .then((response) => {
      if (!response.ok) {
        throw new Error(`無法取得目錄資料（HTTP 狀態碼 ${response.status}）`);
      }
      return response.json();
    })
    .then((notes) => {
      if (!Array.isArray(notes)) {
        throw new Error('目錄資料格式錯誤：預期為陣列');
      }

      // 清空容器（使用 textContent 清空，完全不用 innerHTML）
      container.textContent = '';

      if (notes.length === 0) {
        const emptyP = document.createElement('p');
        emptyP.className = 'empty-message';
        emptyP.textContent = '尚無筆記';
        container.appendChild(emptyP);
        return;
      }

      // 依年份分組
      const groups = new Map();
      for (const item of notes) {
        const year = item.year;
        if (!groups.has(year)) {
          groups.set(year, []);
        }
        groups.get(year).push(item);
      }

      // 年份由大到小排序
      const sortedYears = Array.from(groups.keys()).sort((a, b) => b - a);

      for (const year of sortedYears) {
        const section = document.createElement('section');
        section.className = 'year-section';

        const yearHeading = document.createElement('h2');
        yearHeading.className = 'year-title';
        yearHeading.textContent = `${year} 年`;
        section.appendChild(yearHeading);

        const ul = document.createElement('ul');
        ul.className = 'notes-card-list';

        for (const item of groups.get(year)) {
          const li = document.createElement('li');
          li.className = 'note-card';

          // 標題連結（點擊進入筆記頁）
          const titleLink = document.createElement('a');
          titleLink.className = 'note-card-title';
          titleLink.href = item.path;
          titleLink.textContent = item.title;

          // 年份標籤
          const metaDiv = document.createElement('div');
          metaDiv.className = 'note-card-meta';
          const yearSpan = document.createElement('span');
          yearSpan.className = 'note-card-year';
          yearSpan.textContent = `年份：${item.year}`;
          metaDiv.appendChild(yearSpan);

          // 一句摘要
          const summaryP = document.createElement('p');
          summaryP.className = 'note-card-summary';
          summaryP.textContent = item.summary;

          li.appendChild(titleLink);
          li.appendChild(metaDiv);
          li.appendChild(summaryP);
          ul.appendChild(li);
        }

        section.appendChild(ul);
        container.appendChild(section);
      }
    })
    .catch((error) => {
      // 載入失敗或解析錯誤時顯示錯誤訊息
      container.textContent = '';
      const errorP = document.createElement('p');
      errorP.className = 'error-message';
      errorP.textContent = `目錄載入失敗：${error.message}`;
      container.appendChild(errorP);
    });
});

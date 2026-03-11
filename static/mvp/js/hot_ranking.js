const topicInput = document.getElementById("topicInput");
const startDateInput = document.getElementById("startDate");
const endDateInput = document.getElementById("endDate");
const searchBtn = document.getElementById("searchBtn");
const eventsBody = document.getElementById("eventsBody");
const rankingList = document.getElementById("rankingList");
const prevPage = document.getElementById("prevPage");
const nextPage = document.getElementById("nextPage");
const pageInfo = document.getElementById("pageInfo");

let currentPage = 1;
let totalPages = 1;

function riskClass(ri) {
  if (ri >= 80) return "risk-high";
  if (ri >= 50) return "risk-mid";
  return "risk-low";
}

function currentFilters() {
  return {
    topic: encodeURIComponent(topicInput.value.trim()),
    startDate: startDateInput.value,
    endDate: endDateInput.value,
  };
}

function renderEvents(items) {
  if (!items.length) {
    eventsBody.innerHTML = '<tr><td colspan="5">暂无数据</td></tr>';
    return;
  }
  eventsBody.innerHTML = items
    .map((item) => {
      const content = (item.content || "").replace(/\s+/g, " ").trim();
      return `
      <tr>
        <td>${item.create_time || "-"}</td>
        <td>${item.topic_name || "-"}</td>
        <td class="content-ellipsis" title="${content}">${content || "-"}</td>
        <td>${item.liked_count}/${item.comments_count}/${item.shared_count}</td>
        <td><span class="risk-badge ${riskClass(item.risk_index)}">${item.risk_index}</span></td>
      </tr>`;
    })
    .join("");
}

function renderRanking(items) {
  if (!items.length) {
    rankingList.innerHTML = "<div>暂无排行数据</div>";
    return;
  }
  rankingList.innerHTML = items
    .map(
      (item, idx) => `
      <div class="rank-item">
        <div>#${idx + 1} ${item.topic_name || "未分类"} <span class="rank-score">${item.heat_score}</span></div>
        <div>${item.nickname || "匿名用户"} · ${item.create_time || "-"}</div>
      </div>
    `
    )
    .join("");
}

async function loadEvents() {
  const f = currentFilters();
  try {
    eventsBody.innerHTML = '<tr><td colspan="5"><div class="skeleton"></div></td></tr>';
    const data = await apiGet(
      `/mvp/api/hot-events?page=${currentPage}&page_size=10&topic=${f.topic}&start_date=${f.startDate}&end_date=${f.endDate}&platform=weibo`
    );
    renderEvents(data.data || []);
    totalPages = data.pagination.total_pages || 1;
    pageInfo.textContent = `第 ${currentPage} / ${totalPages} 页`;
  } catch (err) {
    eventsBody.innerHTML = `<tr><td colspan="5">加载失败：${err.message}</td></tr>`;
  }
}

async function loadRanking() {
  const f = currentFilters();
  showSkeleton(rankingList, 5);
  try {
    const data = await apiGet(
      `/mvp/api/ranking?top_n=10&topic=${f.topic}&start_date=${f.startDate}&end_date=${f.endDate}`
    );
    renderRanking(data.data || []);
  } catch (err) {
    rankingList.innerHTML = `<div>加载失败：${err.message}</div>`;
  }
}

async function loadAll() {
  await Promise.all([loadEvents(), loadRanking()]);
}

searchBtn.addEventListener("click", () => {
  currentPage = 1;
  loadAll();
});

prevPage.addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage -= 1;
    loadEvents();
  }
});

nextPage.addEventListener("click", () => {
  if (currentPage < totalPages) {
    currentPage += 1;
    loadEvents();
  }
});

formatDateInputDefaults(startDateInput, endDateInput, 30);
loadAll();

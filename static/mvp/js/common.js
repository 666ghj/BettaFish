function formatDateInputDefaults(startInput, endInput, days = 30) {
  const endDate = new Date();
  const startDate = new Date();
  startDate.setDate(endDate.getDate() - (days - 1));

  const toDateString = (d) => d.toISOString().slice(0, 10);
  if (startInput && !startInput.value) startInput.value = toDateString(startDate);
  if (endInput && !endInput.value) endInput.value = toDateString(endDate);
}

function showSkeleton(container, rows = 4) {
  if (!container) return;
  container.innerHTML = "";
  for (let i = 0; i < rows; i += 1) {
    const div = document.createElement("div");
    div.className = "skeleton";
    container.appendChild(div);
  }
}

async function apiGet(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok || !data.success) {
    throw new Error(data.message || "请求失败");
  }
  return data;
}

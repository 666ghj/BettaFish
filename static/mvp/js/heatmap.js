const startDateInput = document.getElementById("startDate");
const endDateInput = document.getElementById("endDate");
const loadHeatmapBtn = document.getElementById("loadHeatmapBtn");
const regionList = document.getElementById("regionList");
const mapChart = echarts.init(document.getElementById("chinaMap"));

let chinaMapLoaded = false;

async function ensureChinaMap() {
  if (chinaMapLoaded) return;
  const mapJson = await fetch("https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json").then((r) => r.json());
  echarts.registerMap("china", mapJson);
  chinaMapLoaded = true;
}

function renderRegionRanking(list) {
  if (!list.length) {
    regionList.innerHTML = "<div>暂无地区数据</div>";
    return;
  }
  const sorted = [...list].sort((a, b) => b.value - a.value).slice(0, 12);
  regionList.innerHTML = sorted
    .map(
      (r, idx) => `
      <div class="rank-item">
        <div>#${idx + 1} ${r.name}<span class="rank-score">${r.value}</span></div>
        <div>事件数：${r.event_count || 0}</div>
      </div>
      `
    )
    .join("");
}

async function loadHeatmap() {
  showSkeleton(regionList, 6);
  try {
    await ensureChinaMap();
    const data = await apiGet(
      `/mvp/api/heatmap-china?start_date=${startDateInput.value}&end_date=${endDateInput.value}`
    );

    const mapData = data.data || [];
    renderRegionRanking(mapData);

    mapChart.setOption(
      {
        animationDuration: 320,
        animationEasing: "cubicOut",
        tooltip: {
          trigger: "item",
          formatter: (params) => `${params.name}<br/>RI: ${params.value || 0}`,
        },
        visualMap: {
          min: 0,
          max: 100,
          text: ["高风险", "低风险"],
          calculable: true,
          inRange: {
            color: ["#b3f4d8", "#fed784", "#ff6b8a"],
          },
          textStyle: { color: "#dbe7ff" },
        },
        series: [
          {
            name: "风险热力",
            type: "map",
            map: "china",
            roam: true,
            emphasis: {
              itemStyle: { areaColor: "#7ea9ff" },
              label: { color: "#fff" },
            },
            itemStyle: {
              borderColor: "rgba(255,255,255,0.3)",
              borderWidth: 1,
            },
            data: mapData,
          },
        ],
      },
      true
    );
  } catch (err) {
    regionList.innerHTML = `<div>加载失败：${err.message}</div>`;
  }
}

window.addEventListener("resize", () => mapChart.resize());
loadHeatmapBtn.addEventListener("click", loadHeatmap);

formatDateInputDefaults(startDateInput, endDateInput, 30);
loadHeatmap();

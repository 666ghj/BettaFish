const topicInput = document.getElementById("topicInput");
const startDateInput = document.getElementById("startDate");
const endDateInput = document.getElementById("endDate");
const loadTrendBtn = document.getElementById("loadTrendBtn");

const riskChart = echarts.init(document.getElementById("riskChart"));
const countChart = echarts.init(document.getElementById("countChart"));

function requestUrl() {
  const topic = encodeURIComponent(topicInput.value.trim());
  return `/mvp/api/trend-30d?topic=${topic}&start_date=${startDateInput.value}&end_date=${endDateInput.value}`;
}

function setChart(chart, title, dates, values, color) {
  chart.setOption(
    {
      animationDuration: 300,
      animationEasing: "cubicOut",
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: "#c3d0f2" },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#c3d0f2" },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
      },
      series: [
        {
          name: title,
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 3, color },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}80` },
              { offset: 1, color: `${color}10` },
            ]),
          },
          data: values,
        },
      ],
    },
    true
  );
}

async function loadTrend() {
  try {
    const data = await apiGet(requestUrl());
    const dates = data.data.dates || [];
    setChart(riskChart, "RI", dates, data.data.risk_index || [], "#74a6ff");
    setChart(countChart, "话题数", dates, data.data.topic_counts || [], "#67e8f9");
  } catch (err) {
    riskChart.setOption({ title: { text: `加载失败: ${err.message}`, left: "center", textStyle: { color: "#fff" } } });
    countChart.setOption({ title: { text: `加载失败: ${err.message}`, left: "center", textStyle: { color: "#fff" } } });
  }
}

window.addEventListener("resize", () => {
  riskChart.resize();
  countChart.resize();
});

loadTrendBtn.addEventListener("click", loadTrend);
formatDateInputDefaults(startDateInput, endDateInput, 30);
loadTrend();

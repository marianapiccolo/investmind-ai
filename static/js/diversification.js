document.addEventListener("DOMContentLoaded", () => {
  renderAssetTypeChart();
  renderSectorChart();
});

function readDiversificationJson(elementId) {
  const element = document.getElementById(elementId);

  if (!element) {
    return null;
  }

  return JSON.parse(element.textContent);
}

function renderAssetTypeChart() {
  const canvas = document.getElementById("assetTypeChart");

  const data = readDiversificationJson("asset-type-chart-data");

  if (!canvas || !data) {
    return;
  }

  const palette = [
    "#16324f",
    "#276a57",
    "#a98755",
    "#667085",
    "#7895a8",
    "#7f6d8d",
  ];

  new Chart(canvas, {
    type: "doughnut",

    data: {
      labels: data.labels,

      datasets: [
        {
          data: data.values,

          backgroundColor: data.labels.map(
            (_, index) => palette[index % palette.length]
          ),

          borderColor: "#ffffff",

          borderWidth: 4,

          hoverOffset: 4,
        },
      ],
    },

    options: {
      responsive: true,

      maintainAspectRatio: false,

      cutout: "72%",

      plugins: {
        legend: {
          display: false,
        },

        tooltip: {
          callbacks: {
            label(context) {
              return `${context.label}: ${InvestMindNumbers.percentage(context.parsed)}`;
            },
          },
        },
      },
    },
  });
}

function renderSectorChart() {
  const canvas = document.getElementById("sectorChart");

  const data = readDiversificationJson("sector-chart-data");

  if (!canvas || !data) {
    return;
  }

  new Chart(canvas, {
    type: "bar",

    data: {
      labels: data.labels,

      datasets: [
        {
          data: data.values,

          backgroundColor: "#16324f",

          borderRadius: 5,

          borderSkipped: false,

          maxBarThickness: 34,
        },
      ],
    },

    options: {
      indexAxis: "y",

      responsive: true,

      maintainAspectRatio: false,

      plugins: {
        legend: {
          display: false,
        },

        tooltip: {
          callbacks: {
            label(context) {
              return InvestMindNumbers.percentage(context.parsed.x);
            },
          },
        },
      },

      scales: {
        x: {
          beginAtZero: true,

          suggestedMax: 100,

          grid: {
            color: "#edf0f3",
          },

          ticks: {
            color: "#98a2b3",

            font: {
              size: 10,
            },

            callback(value) {
              return InvestMindNumbers.percentage(value, { minimumFractionDigits: 0 });
            },
          },
        },

        y: {
          grid: {
            display: false,
          },

          ticks: {
            color: "#667085",

            font: {
              size: 11,
            },
          },
        },
      },
    },
  });
}

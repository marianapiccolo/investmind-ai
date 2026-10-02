document.addEventListener("DOMContentLoaded", () => {
  renderPerformanceChart();
  renderCompositionChart();
});

function readJsonScript(elementId) {
  const element = document.getElementById(elementId);

  if (!element) {
    return null;
  }

  return JSON.parse(element.textContent);
}

function renderPerformanceChart() {
  const canvas = document.getElementById("performanceChart");

  const data = readJsonScript("performance-chart-data");

  if (!canvas || !data) {
    return;
  }

  new Chart(canvas, {
    type: "line",

    data: {
      labels: data.labels,

      datasets: [
        {
          label: "Cumulative TWR (%)",

          data: data.values,

          borderColor: "#16324f",

          backgroundColor: "rgba(22, 50, 79, 0.08)",

          borderWidth: 2,

          pointRadius: 2,

          pointHoverRadius: 5,

          pointBackgroundColor: "#16324f",

          tension: 0.28,

          fill: true,
        },
      ],
    },

    options: {
      responsive: true,

      maintainAspectRatio: false,

      interaction: {
        mode: "index",
        intersect: false,
      },

      plugins: {
        legend: {
          display: false,
        },

        tooltip: {
          callbacks: {
            label(context) {
              const value = context.parsed.y;

              const sign = value > 0 ? "+" : "";

              return `${sign}` + `${value.toFixed(2)}%`;
            },
          },
        },
      },

      scales: {
        x: {
          grid: {
            display: false,
          },

          ticks: {
            color: "#98a2b3",

            maxTicksLimit: 6,

            font: {
              size: 10,
            },
          },
        },

        y: {
          grid: {
            color: "#edf0f3",
          },

          ticks: {
            color: "#98a2b3",

            font: {
              size: 10,
            },

            callback(value) {
              return `${value}%`;
            },
          },
        },
      },
    },
  });
}

function renderCompositionChart() {
  const canvas = document.getElementById("compositionChart");

  const data = readJsonScript("composition-chart-data");

  if (!canvas || !data) {
    return;
  }

  const palette = [
    "#16324f",
    "#276a57",
    "#a98755",
    "#667085",
    "#49687f",
    "#78998b",
    "#b9a482",
  ];

  new Chart(canvas, {
    type: "doughnut",

    data: {
      labels: data.labels,

      datasets: [
        {
          data: data.values,

          backgroundColor: data.values.map(
            (_, index) => palette[index % palette.length]
          ),

          borderColor: "#ffffff",

          borderWidth: 3,

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
              return `${context.label}: ` + `${context.parsed.toFixed(2)}%`;
            },
          },
        },
      },
    },
  });
}

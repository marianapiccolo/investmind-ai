document.addEventListener("DOMContentLoaded", () => {
  renderCumulativePerformance();
  renderDailyReturns();
});

function readPerformanceJson(elementId) {
  const element = document.getElementById(elementId);

  if (!element) {
    return null;
  }

  return JSON.parse(element.textContent);
}

function renderCumulativePerformance() {
  const canvas = document.getElementById("performancePageChart");

  const data = readPerformanceJson("performance-page-chart-data");

  if (!canvas || !data) {
    return;
  }

  new Chart(canvas, {
    type: "line",

    data: {
      labels: data.labels,

      datasets: [
        {
          data: data.values,

          borderColor: "#16324f",

          backgroundColor: "rgba(22, 50, 79, 0.08)",

          borderWidth: 2,

          pointRadius: 3,

          pointHoverRadius: 6,

          pointBackgroundColor: "#16324f",

          tension: 0.25,

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

              return InvestMindNumbers.percentage(value, { signed: true });
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
            maxTicksLimit: 8,

            color: "#98a2b3",

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
              return InvestMindNumbers.percentage(value, { minimumFractionDigits: 0 });
            },
          },
        },
      },
    },
  });
}

function renderDailyReturns() {
  const canvas = document.getElementById("dailyReturnChart");

  const data = readPerformanceJson("daily-return-chart-data");

  if (!canvas || !data) {
    return;
  }

  const colors = data.values.map((value) => {
    if (value === null) {
      return "#e3e8ef";
    }

    return value >= 0 ? "#276a57" : "#9a4545";
  });

  new Chart(canvas, {
    type: "bar",

    data: {
      labels: data.labels,

      datasets: [
        {
          data: data.values,

          backgroundColor: colors,

          borderRadius: 4,

          borderSkipped: false,
        },
      ],
    },

    options: {
      responsive: true,

      maintainAspectRatio: false,

      plugins: {
        legend: {
          display: false,
        },

        tooltip: {
          callbacks: {
            label(context) {
              const value = context.parsed.y;

              if (value === null) {
                return "No return available";
              }

              return InvestMindNumbers.percentage(value, { signed: true });
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
            maxTicksLimit: 8,

            color: "#98a2b3",

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
              return InvestMindNumbers.percentage(value, { minimumFractionDigits: 0 });
            },
          },
        },
      },
    },
  });
}

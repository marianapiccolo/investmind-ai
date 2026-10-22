document.addEventListener("DOMContentLoaded", () => {
  renderRiskDistribution();
  renderExtremeReturns();
});

function readRiskJson(elementId) {
  const element = document.getElementById(elementId);

  if (!element) {
    return null;
  }

  return JSON.parse(element.textContent);
}

function renderRiskDistribution() {
  const canvas = document.getElementById("riskDistributionChart");

  const data = readRiskJson("risk-distribution-chart-data");

  if (!canvas || !data) {
    return;
  }

  new Chart(canvas, {
    type: "doughnut",

    data: {
      labels: data.labels,

      datasets: [
        {
          data: data.values,

          backgroundColor: ["#276a57", "#9a4545"],

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
              return `${context.label}: ${InvestMindNumbers.number(context.parsed, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
            },
          },
        },
      },
    },
  });
}

function renderExtremeReturns() {
  const canvas = document.getElementById("extremeReturnChart");

  const data = readRiskJson("extreme-return-chart-data");

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

          backgroundColor: ["#276a57", "#9a4545"],

          borderRadius: 6,

          borderSkipped: false,

          maxBarThickness: 86,
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
            color: "#667085",

            font: {
              size: 11,
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

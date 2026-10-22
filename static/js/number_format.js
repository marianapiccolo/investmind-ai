(() => {
  "use strict";

  function number(value, {
    minimumFractionDigits = 2,
    maximumFractionDigits = 2,
    signed = false,
  } = {}) {
    if (
      (typeof value !== "number" && typeof value !== "string") ||
      (typeof value === "string" && value.trim() === "")
    ) {
      return "Unavailable";
    }

    const numericValue = Number(value);

    if (!Number.isFinite(numericValue)) {
      return "Unavailable";
    }

    return new Intl.NumberFormat("en-US", {
      useGrouping: true,
      minimumFractionDigits,
      maximumFractionDigits,
      signDisplay: signed ? "exceptZero" : "auto",
    }).format(numericValue);
  }

  function percentage(value, options = {}) {
    const formatted = number(value, options);

    return formatted === "Unavailable" ? formatted : `${formatted}%`;
  }

  window.InvestMindNumbers = Object.freeze({ number, percentage });
})();

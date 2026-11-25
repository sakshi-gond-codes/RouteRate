/*
 * Chart.js helpers. Charts read their data from <script type="application/json"> blocks
 * rendered by Django (json_script), so no data is hard-coded in JavaScript.
 *
 * Style rules: thin bars with rounded data ends, one value axis, quiet grid,
 * legend whenever there is more than one series, hover tooltips on every chart.
 */
(function () {
  "use strict";
  if (!window.Chart) return;

  const INK = { primary: "#18202f", secondary: "#52514e", muted: "#898781", grid: "#e9ebf0", axis: "#c3c2b7" };
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = INK.secondary;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.legend.labels.useBorderRadius = true;
  Chart.defaults.plugins.legend.labels.borderRadius = 3;
  Chart.defaults.plugins.tooltip.backgroundColor = "#0f1830";
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.maintainAspectRatio = false;

  function read(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function bar(color) {
    return {
      backgroundColor: color, borderColor: "#ffffff", borderWidth: { top: 0, right: 0, bottom: 0, left: 0 },
      borderRadius: 4, borderSkipped: "start", maxBarThickness: 26, categoryPercentage: 0.7, barPercentage: 0.9,
    };
  }

  function axes(opts = {}) {
    const valueAxis = {
      beginAtZero: true, grid: { color: INK.grid, drawTicks: false }, border: { display: false },
      ticks: { color: INK.muted, padding: 6, ...(opts.valueTicks || {}) },
      title: opts.valueTitle ? { display: true, text: opts.valueTitle, color: INK.muted } : undefined,
      stacked: !!opts.stacked,
    };
    const catAxis = {
      grid: { display: false }, border: { color: INK.axis }, ticks: { color: INK.secondary, autoSkip: false },
      stacked: !!opts.stacked,
    };
    return opts.horizontal ? { x: valueAxis, y: catAxis } : { x: catAxis, y: valueAxis };
  }

  const fmtRate = (v) => "$" + Number(v).toFixed(4);
  const make = (id, config) => {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    return new Chart(canvas, config);
  };

  window.RouteRateCharts = {
    // Dashboard: prefixes each vendor prices vs how many it wins as primary route
    vendorCoverage(id, dataId, colors) {
      const d = read(dataId);
      if (!d) return;
      make(id, {
        type: "bar",
        data: {
          labels: d.labels,
          datasets: [
            { label: "Prefixes priced", data: d.quoted, ...bar(colors[0]) },
            { label: "Primary route wins", data: d.wins, ...bar(colors[1]) },
          ],
        },
        options: {
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { position: "top", align: "end" } },
          scales: axes({ valueTitle: "Prefixes" }),
        },
      });
    },

    // Dashboard: rows accepted / duplicates / rejected for recent decks (status colours)
    deckOutcomes(id, dataId, status) {
      const d = read(dataId);
      if (!d) return;
      const seg = (color) => ({ ...bar(color), borderWidth: 1, borderColor: "#ffffff", borderSkipped: false, borderRadius: 0 });
      make(id, {
        type: "bar",
        data: {
          labels: d.labels,
          datasets: [
            { label: "Accepted rows", data: d.accepted, ...seg(status.good) },
            { label: "Duplicates removed", data: d.duplicates, ...seg(status.serious) },
            { label: "Rejected rows", data: d.rejected, ...seg(status.critical) },
          ],
        },
        options: {
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { position: "top", align: "end" } },
          scales: axes({ stacked: true, valueTitle: "Rows" }),
        },
      });
    },

    // Reports: single-series horizontal bars
    horizontal(id, labels, values, color, valueFormatter, valueTitle) {
      make(id, {
        type: "bar",
        data: { labels, datasets: [{ label: valueTitle, data: values, ...bar(color) }] },
        options: {
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (ctx) => ` ${valueTitle}: ${valueFormatter(ctx.raw)}` } },
          },
          scales: axes({ horizontal: true, valueTitle, valueTicks: { callback: (v) => valueFormatter(v) } }),
        },
      });
    },

    // Reports: rate decreases vs increases per vendor
    rateChanges(id, d) {
      make(id, {
        type: "bar",
        data: {
          labels: d.labels,
          datasets: [
            { label: "Decreases", data: d.decreases, ...bar("#2a78d6") },
            { label: "Increases", data: d.increases, ...bar("#e34948") },
          ],
        },
        options: {
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { position: "top", align: "end" } },
          scales: axes({ valueTitle: "Prefixes" }),
        },
      });
    },

    read, fmtRate,
  };
})();

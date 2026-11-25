/*
 * Column mapping page.
 * - Highlights the preview column chosen for each field and labels it
 * - Warns when one column is used twice or a required field is missing
 * - Shows a live sample value for each field
 */
(function () {
  "use strict";
  const selects = Array.from(document.querySelectorAll("select.map-select"));
  const table = document.getElementById("map-preview");
  const submit = document.getElementById("process-btn");
  const status = document.getElementById("map-status");
  if (!selects.length || !table) return;

  const headers = Array.from(table.querySelectorAll("thead th[data-col]"));
  const labelFor = {};
  selects.forEach((s) => {
    labelFor[s.dataset.field] = s.closest(".field-row").querySelector("label").textContent.replace("*", "").trim();
  });

  function columnIndex(name) {
    return headers.findIndex((th) => th.dataset.col === name);
  }

  function sampleValue(colIdx) {
    for (const row of table.querySelectorAll("tbody tr")) {
      const cell = row.querySelectorAll("td[data-idx]")[colIdx];
      if (cell && cell.textContent.trim()) return cell.textContent.trim();
    }
    return "";
  }

  function refresh() {
    table.querySelectorAll(".mapped").forEach((el) => el.classList.remove("mapped"));
    table.querySelectorAll(".map-tag").forEach((el) => el.remove());

    const used = {};
    const problems = [];
    selects.forEach((s) => {
      const sample = s.closest(".field-row").querySelector(".sample");
      const col = s.value;
      s.classList.remove("is-invalid");
      if (!col) {
        sample.textContent = s.required ? "Required" : "";
        sample.className = "sample small " + (s.required ? "text-danger" : "text-body-secondary");
        if (s.required) { problems.push(`${labelFor[s.dataset.field]} is required`); s.classList.add("is-invalid"); }
        return;
      }
      if (used[col]) {
        problems.push(`'${col}' is used for both ${used[col]} and ${labelFor[s.dataset.field]}`);
        s.classList.add("is-invalid");
      }
      used[col] = labelFor[s.dataset.field];

      const idx = columnIndex(col);
      if (idx >= 0) {
        const th = headers[idx];
        th.classList.add("mapped");
        const tag = document.createElement("span");
        tag.className = "map-tag";
        tag.textContent = labelFor[s.dataset.field];
        th.appendChild(tag);
        table.querySelectorAll("tbody tr").forEach((row) => {
          const cell = row.querySelectorAll("td[data-idx]")[idx];
          if (cell) cell.classList.add("mapped");
        });
        const value = sampleValue(idx);
        sample.textContent = value ? `e.g. ${value}` : "column is empty in the preview";
        sample.className = "sample small mono text-body-secondary";
      }
    });

    if (problems.length) {
      status.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i>' + problems.join(" · ");
      status.className = "small text-danger";
      submit.disabled = true;
    } else {
      status.innerHTML = '<i class="bi bi-check-circle me-1"></i>Mapping looks good';
      status.className = "small text-success";
      submit.disabled = false;
    }
  }

  selects.forEach((s) => s.addEventListener("change", refresh));
  refresh();
})();

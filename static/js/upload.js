/* Drag-and-drop file picker for the rate deck upload page. */
(function () {
  "use strict";
  const zone = document.getElementById("drop-zone");
  const input = document.querySelector('input[type="file"][name="file"]');
  const label = document.getElementById("drop-file-name");
  if (!zone || !input) return;

  const allowed = [".csv", ".xlsx", ".xlsm", ".txt"];
  const maxMb = Number(zone.dataset.maxMb || 10);

  function show(file) {
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    const sizeMb = file.size / 1024 / 1024;
    let note = `${file.name} · ${sizeMb < 1 ? (file.size / 1024).toFixed(0) + " KB" : sizeMb.toFixed(1) + " MB"}`;
    zone.classList.remove("border-danger");
    if (!allowed.includes(ext)) { note = `${file.name}: only .csv and .xlsx files are supported`; zone.classList.add("border-danger"); }
    else if (sizeMb > maxMb) { note = `${file.name} is larger than ${maxMb} MB`; zone.classList.add("border-danger"); }
    label.textContent = note;
  }

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  input.addEventListener("change", () => show(input.files[0]));
  ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (e) => {
    e.preventDefault(); zone.classList.add("dragover");
  }));
  ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, (e) => {
    e.preventDefault(); zone.classList.remove("dragover");
  }));
  zone.addEventListener("drop", (e) => {
    if (!e.dataTransfer.files.length) return;
    input.files = e.dataTransfer.files;
    show(input.files[0]);
  });
})();

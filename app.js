document.addEventListener("DOMContentLoaded", () => {
  const format = (value, digits = 2) => new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number.isFinite(value) ? value : 0);
  let currency = document.querySelector("#currency-select")?.value
    || document.querySelector('meta[name="currency-code"]')?.content
    || "EUR";
  const formatMoney = value => new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);

  const productRows = document.querySelector("#product-rows");
  const search = document.querySelector("#product-search");
  const filter = document.querySelector("#product-filter");
  const sort = document.querySelector("#product-sort");
  let refreshGridView = () => {};

  if (productRows && search && filter) {
    const allRows = [...productRows.querySelectorAll(".product-row")];
    const filterRows = () => {
      const query = search.value.trim().toLocaleLowerCase("fr");
      const status = filter.value;
      const mode = sort?.value || "recent";
      const sorted = [...allRows].sort((a, b) => {
        if (mode === "name") return a.dataset.name.localeCompare(b.dataset.name, "fr");
        if (mode === "profit-desc") return Number(b.dataset.profit) - Number(a.dataset.profit);
        if (mode === "margin-desc") return Number(b.dataset.margin) - Number(a.dataset.margin);
        return Number(a.dataset.order) - Number(b.dataset.order);
      });
      sorted.forEach((row, index) => {
        row.querySelector(".index-cell").textContent = String(index + 1);
        row.hidden = !row.dataset.name.includes(query)
          || (status !== "all" && row.dataset.status !== status);
        productRows.appendChild(row);
      });
      const visible = sorted.filter(row => !row.hidden).length;
      document.querySelector("#result-count").textContent = `${visible} ligne${visible === 1 ? "" : "s"}`;
      document.querySelector("#no-results").hidden = visible !== 0;
    };
    refreshGridView = filterRows;
    search.addEventListener("input", filterRows);
    filter.addEventListener("change", filterRows);
    sort?.addEventListener("change", filterRows);
  }

  const currencySelect = document.querySelector("#currency-select");
  currencySelect?.addEventListener("change", async () => {
    const previous = currency;
    const message = document.querySelector("#save-message");
    message.textContent = "Mise à jour de la devise…";
    try {
      const response = await fetch("/api/preferences/devise", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
        },
        body: JSON.stringify({ currency: currencySelect.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Impossible d’enregistrer la devise.");
      currency = result.currency;
      document.querySelectorAll(".currency-label").forEach(label => { label.textContent = currency; });
      productRows?.querySelectorAll(".product-row").forEach(calculateRow);
      message.textContent = `Devise ${currency} enregistrée · aucune conversion appliquée`;
    } catch (error) {
      currencySelect.value = previous;
      message.textContent = error.message || "Erreur lors de l’enregistrement de la devise";
    }
  });

  const money = document.querySelector("#summary-profit");
  const updateSummary = () => {
    if (!productRows) return;
    const rows = [...productRows.querySelectorAll(".product-row")];
    const total = rows.reduce((sum, row) => sum + Number(row.dataset.profit || 0), 0);
    const profitable = rows.filter(row => row.dataset.status === "profit").length;
    const margins = rows.map(row => Number(row.dataset.margin || 0));
    const average = margins.length ? margins.reduce((sum, value) => sum + value, 0) / margins.length : 0;
    if (money) money.textContent = formatMoney(total);
    const profitableNode = document.querySelector("#summary-profitable");
    const marginNode = document.querySelector("#summary-margin");
    if (profitableNode) profitableNode.textContent = String(profitable);
    if (marginNode) marginNode.textContent = format(average, 1);
  };

  const calculateRow = row => {
    const value = field => Number(row.querySelector(`[data-field="${field}"]`).value) || 0;
    const purchase = value("purchase_ht");
    const sale = value("sale_ht");
    const vat = value("vat_rate");
    const extra = value("extra_cost_ht");
    const quantity = Math.max(1, value("quantity"));
    const factor = 1 + vat / 100;
    const profitUnit = sale - purchase - extra;
    const profitTotal = profitUnit * quantity;
    const cost = purchase + extra;
    const margin = cost ? profitUnit / cost * 100 : 0;
    row.dataset.name = [
      row.querySelector(".name-cell").textContent,
      ...["product_code", "barcode", "supplier"].map(field => row.querySelector(`[data-field="${field}"]`).value),
    ].join(" ").toLocaleLowerCase("fr");
    const outputs = {
      purchase_ttc: formatMoney(purchase * factor),
      sale_ttc: formatMoney(sale * factor),
      extra_ttc: formatMoney(extra * factor),
      profit_unit: formatMoney(profitUnit),
      profit_total: formatMoney(profitTotal),
      margin: `${format(margin, 1)} %`,
    };
    for (const [key, text] of Object.entries(outputs)) {
      row.querySelector(`[data-output="${key}"]`).textContent = text;
    }
    const profitCell = row.querySelector('[data-output="profit_total"]');
    profitCell.classList.toggle("negative", profitTotal < 0);
    profitCell.classList.toggle("positive", profitTotal >= 0);
    const status = profitTotal > 0 ? "profit" : profitTotal < 0 ? "loss" : "even";
    row.dataset.profit = String(profitTotal);
    row.dataset.margin = String(margin);
    row.dataset.status = status;
    const badge = row.querySelector('[data-output="status"]');
    badge.textContent = status === "profit" ? "Rentable" : status === "loss" ? "À perte" : "Équilibre";
    badge.classList.toggle("status-profit", status === "profit");
    badge.classList.toggle("status-loss", status === "loss");
    badge.classList.toggle("status-even", status === "even");
    updateSummary();
  };

  const saveRow = async row => {
    if (row.dataset.saving === "true") {
      row.dataset.saveAgain = "true";
      return;
    }
    row.dataset.saving = "true";
    const message = document.querySelector("#save-message");
    const statusCell = row.querySelector(".status-cell");
    statusCell.classList.add("is-saving");
    message.textContent = "Enregistrement…";
    try {
      do {
        row.dataset.saveAgain = "false";
        const data = Object.fromEntries([...row.querySelectorAll("[data-field]")]
          .map(input => [input.dataset.field, input.value]));
        const response = await fetch(`/api/produit/${row.dataset.id}/cellules`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
          },
          body: JSON.stringify(data),
        });
        if (!response.ok) {
          const result = await response.json();
          throw new Error(result.error || "Enregistrement impossible.");
        }
      } while (row.dataset.saveAgain === "true");
      message.textContent = "Toutes les modifications sont enregistrées";
      statusCell.classList.remove("is-saving", "save-error");
      statusCell.classList.add("is-saved");
      refreshGridView();
      window.setTimeout(() => statusCell.classList.remove("is-saved"), 1200);
    } catch (error) {
      message.textContent = error.message || "Erreur lors de l’enregistrement";
      statusCell.classList.remove("is-saving");
      statusCell.classList.add("save-error");
    } finally {
      row.dataset.saving = "false";
    }
  };

  productRows?.querySelectorAll(".product-row").forEach(row => {
    row.querySelectorAll("[data-field]").forEach(input => {
      input.addEventListener("input", () => {
        calculateRow(row);
        document.querySelector("#save-message").textContent = "Valeur modifiée · quitte la cellule pour enregistrer";
      });
      input.addEventListener("change", () => saveRow(row));
      if (input.dataset.field === "barcode") {
        input.addEventListener("keydown", event => {
          if (event.key === "Enter") {
            event.preventDefault();
            input.blur();
          }
        });
      }
    });
  });

  const priceForm = document.querySelector("#product-form");
  if (priceForm) {
    const input = name => priceForm.elements.namedItem(name);
    const refresh = () => {
      const purchase = Number(input("purchase_ttc").value) || 0;
      const sale = Number(input("sale_ttc").value) || 0;
      const expenses = Number(input("extra_cost_ttc").value) || 0;
      const vat = Number(input("vat_rate").value) || 0;
      const quantity = Number(input("quantity").value) || 1;
      const factor = 1 + vat / 100;
      const profitUnit = (sale - purchase - expenses) / factor;
      const profitTotal = profitUnit * quantity;
      const base = (purchase + expenses) / factor;
      const margin = base ? profitUnit / base * 100 : 0;
      document.querySelector("#preview-sale-ht").textContent = formatMoney(sale / factor);
      document.querySelector("#preview-cost-ht").textContent = formatMoney(base);
      document.querySelector("#preview-profit").textContent = formatMoney(profitTotal);
      document.querySelector("#preview-margin").textContent = `${format(margin)} %`;
      document.querySelector("#preview-profit").classList.toggle("negative", profitTotal < 0);
    };
    priceForm.addEventListener("input", refresh);
    refresh();
  }
});

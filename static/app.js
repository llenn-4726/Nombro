document.addEventListener("DOMContentLoaded", () => {
  const language = document.querySelector('meta[name="language"]')?.content || "fr";
  const english = language === "en";
  const locale = language === "en" ? "en-GB" : "fr-FR";
  const offlineUserId = document.querySelector('meta[name="user-id"]')?.content || "browser";
  const pendingGridKey = `nombro-pending-grid:${offlineUserId}`;
  const readPendingGrid = () => {
    try { return JSON.parse(localStorage.getItem(pendingGridKey) || "{}"); }
    catch { return {}; }
  };
  const writePendingGrid = pending => {
    if (Object.keys(pending).length) localStorage.setItem(pendingGridKey, JSON.stringify(pending));
    else localStorage.removeItem(pendingGridKey);
    updateOfflineBanner();
  };
  const offlineBanner = document.createElement("div");
  offlineBanner.className = "offline-banner";
  offlineBanner.setAttribute("role", "status");
  offlineBanner.setAttribute("aria-live", "polite");
  const page = document.querySelector("main.page");
  if (page) page.prepend(offlineBanner);
  const updateOfflineBanner = (message = "") => {
    if (!offlineBanner) return;
    const pendingCount = Object.keys(readPendingGrid()).length;
    const offline = !navigator.onLine;
    offlineBanner.hidden = !offline && !pendingCount && !message;
    offlineBanner.classList.toggle("is-offline", offline);
    offlineBanner.textContent = message || (offline
      ? (english ? "Connection lost. Changes will be kept on this device and sent when the network returns." : "Connexion au serveur perdue. Les changements seront gardés sur cet appareil et envoyés au retour du réseau.")
      : pendingCount
        ? (english ? `${pendingCount} change(s) waiting to sync with the server.` : `${pendingCount} modification(s) en attente d’envoi au serveur.`)
        : "");
  };
  window.addEventListener("offline", () => updateOfflineBanner());
  window.addEventListener("online", () => updateOfflineBanner(english ? "Connection restored. Sending pending changes…" : "Connexion rétablie. Envoi des modifications en attente…"));
  updateOfflineBanner();
  const restoreMode = document.querySelector("#restore-mode");
  const replaceConfirm = document.querySelector("#replace-confirm-row");
  const replaceCheckbox = replaceConfirm?.querySelector('input[type="checkbox"]');
  const updateRestoreWarning = () => {
    const replacing = restoreMode?.value === "replace";
    if (replaceConfirm) replaceConfirm.hidden = !replacing;
    if (replaceCheckbox) replaceCheckbox.required = Boolean(replacing);
  };
  restoreMode?.addEventListener("change", updateRestoreWarning);
  updateRestoreWarning();

  const backupFileInput = document.querySelector("#backup-file-input");
  const backupFileName = document.querySelector("#backup-file-name");
  backupFileInput?.addEventListener("change", () => {
    if (backupFileName) {
      backupFileName.textContent = backupFileInput.files?.[0]?.name
        || (english ? "No file selected." : "Aucun fichier sélectionné.");
    }
  });

  let competitorBrands = [];
  const addPickerOption = (picker, value) => {
    const menu = picker.querySelector(".supplier-menu");
    const addOption = picker.querySelector("[data-supplier-add]");
    if ([...picker.querySelectorAll("[data-supplier-option]")].some(option => option.dataset.value.toLocaleLowerCase("fr") === value.toLocaleLowerCase("fr"))) return;
    const option = document.createElement("button");
    option.type = "button";
    option.className = "supplier-option";
    option.setAttribute("role", "option");
    option.dataset.supplierOption = "";
    option.dataset.value = value;
    option.textContent = value;
    option.title = value;
    if (picker.dataset.brandPicker === "true") {
      const choice = document.createElement("div");
      choice.className = "competitor-brand-choice";
      choice.setAttribute("role", "group");
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "competitor-brand-delete";
      deleteButton.dataset.brandDelete = "";
      deleteButton.dataset.value = value;
      deleteButton.textContent = "×";
      deleteButton.title = `${picker.dataset.deleteBrandLabel || "Remove retailer"}: ${value}`;
      deleteButton.setAttribute("aria-label", `${picker.dataset.deleteBrandLabel || "Remove retailer"}: ${value}`);
      choice.append(option, deleteButton);
      menu.insertBefore(choice, addOption);
    } else {
      menu.insertBefore(option, addOption);
    }
  };
  const deleteCompetitorBrand = async brand => {
    const status = document.querySelector("#competitor-brand-status");
    try {
      const response = await fetch("/api/enseignes/concurrence", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
        },
        body: JSON.stringify({ brand }),
      });
      if (!response.ok) throw new Error();
      competitorBrands = competitorBrands.filter(item => item.toLocaleLowerCase("fr") !== brand.toLocaleLowerCase("fr"));
      document.querySelectorAll(".competitor-brand-picker").forEach(picker => {
        picker.querySelectorAll("[data-supplier-option]").forEach(option => {
          if (option.dataset.value.toLocaleLowerCase("fr") === brand.toLocaleLowerCase("fr")) {
            (option.closest(".competitor-brand-choice") || option).remove();
          }
        });
        const empty = picker.querySelector(".supplier-empty");
        if (empty) empty.hidden = picker.querySelectorAll("[data-supplier-option]:not([hidden])").length > 0;
      });
      if (status) status.textContent = english ? "Retailer removed from suggestions." : "Enseigne supprimée des suggestions.";
    } catch {
      if (status) status.textContent = english ? "Could not remove this retailer. Try again." : "Impossible de supprimer l’enseigne. Réessaie.";
    }
  };
  const initializeSearchablePicker = picker => {
    const input = picker.querySelector("[data-picker-input], input[name=\"supplier\"]");
    const toggle = picker.querySelector(".supplier-picker-toggle");
    const menu = picker.querySelector(".supplier-menu");
    const addOption = picker.querySelector("[data-supplier-add]");
    const emptyMessage = picker.querySelector(".supplier-empty");
    if (!input || !toggle || !menu) return;

    const close = () => {
      menu.hidden = true;
      input.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-expanded", "false");
    };
    const open = (filterByInput = false) => {
      const query = filterByInput ? input.value.trim().toLocaleLowerCase("fr") : "";
      const options = [...picker.querySelectorAll("[data-supplier-option]")];
      let visibleCount = 0;
      let exactMatch = false;
      options.forEach(option => {
        const value = option.dataset.value || "";
        const normalized = value.toLocaleLowerCase("fr");
        option.hidden = Boolean(query && !normalized.includes(query));
        const choice = option.closest(".competitor-brand-choice");
        if (choice) choice.hidden = option.hidden;
        if (!option.hidden) visibleCount += 1;
        if (query && normalized === query) exactMatch = true;
      });
      if (emptyMessage) emptyMessage.hidden = visibleCount > 0;
      if (addOption) {
        const newValue = input.value.trim();
        addOption.hidden = !filterByInput || !newValue || exactMatch;
        addOption.textContent = newValue
          ? `＋ ${picker.dataset.addLabel || (english ? "Add option" : "Ajouter une option")} « ${newValue} »`
          : "";
      }
      menu.hidden = false;
      input.setAttribute("aria-expanded", "true");
      toggle.setAttribute("aria-expanded", "true");
    };
    const choose = (value, wasAdded = false) => {
      input.value = value;
      if (wasAdded && picker.dataset.brandPicker === "true") {
        if (!competitorBrands.some(brand => brand.toLocaleLowerCase("fr") === value.toLocaleLowerCase("fr"))) competitorBrands.push(value);
        document.querySelectorAll(".competitor-brand-picker").forEach(other => addPickerOption(other, value));
      }
      input.focus();
      close();
    };

    toggle.addEventListener("click", () => menu.hidden ? open() : close());
    input.addEventListener("focus", () => open());
    input.addEventListener("input", () => open(true));
    input.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        close();
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        if (menu.hidden) open();
        (menu.querySelector(".supplier-option:not([hidden])") || addOption)?.focus();
      } else if (event.key === "Enter" && !menu.hidden) {
        const firstOption = menu.querySelector("[data-supplier-option]:not([hidden])");
        if (addOption && !addOption.hidden) {
          event.preventDefault();
          choose(input.value.trim(), true);
        } else if (firstOption) {
          event.preventDefault();
          choose(firstOption.dataset.value);
        }
      }
    });
    menu.addEventListener("pointerdown", event => {
      if (event.target.closest("button")) event.preventDefault();
    });
    menu.addEventListener("click", event => {
      const deleteButton = event.target.closest("[data-brand-delete]");
      if (deleteButton) {
        deleteCompetitorBrand(deleteButton.dataset.value || "");
        return;
      }
      const option = event.target.closest("[data-supplier-option]");
      if (option) choose(option.dataset.value);
      if (event.target.closest("[data-supplier-add]")) choose(input.value.trim(), true);
    });
    document.addEventListener("pointerdown", event => {
      if (!picker.contains(event.target)) close();
    });
  };
  document.querySelectorAll(".supplier-picker").forEach(initializeSearchablePicker);

  const competitionSection = document.querySelector("#competition-section");
  let syncCompetitors = () => {};
  if (competitionSection) {
    const rowsContainer = competitionSection.querySelector("#competitor-rows");
    const emptyMessage = competitionSection.querySelector("#competitor-empty");
    const addButton = competitionSection.querySelector("#add-competitor");
    const bulkInput = competitionSection.querySelector("#competitor-bulk-input");
    const bulkButton = competitionSection.querySelector("#add-competitor-bulk");
    const bulkStatus = competitionSection.querySelector("#competitor-bulk-status");
    const hiddenData = competitionSection.querySelector("#competitors-json");
    const productForm = document.querySelector("#product-form");
    const saleInput = productForm?.elements.namedItem("sale_ttc");
    const competitorCurrency = document.querySelector('meta[name="currency-code"]')?.content || "EUR";
    const formatCompetitorMoney = value => new Intl.NumberFormat(locale, {
      style: "currency", currency: competitorCurrency, minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(Number.isFinite(value) ? value : 0);
    const parseLocalizedNumber = value => {
      const normalized = String(value ?? "").replace(/[\s\u00a0\u202f]/g, "").replace(",", ".");
      return normalized ? Number(normalized) : NaN;
    };
    const labels = competitionSection.dataset;
    try {
      competitorBrands = JSON.parse(document.querySelector("#competitor-brand-data")?.textContent || "[]");
    } catch {
      competitorBrands = [];
    }
    let rowCounter = 0;

    const makeField = (labelText, className, type, value, placeholder) => {
      const label = document.createElement("label");
      label.className = `competitor-field ${className}`;
      const title = document.createElement("span");
      title.textContent = labelText;
      const input = document.createElement("input");
      input.type = type;
      input.value = value || "";
      input.placeholder = placeholder || "";
      if (type === "number") {
        input.min = "0";
        input.max = "1000000000";
        input.step = "0.01";
      }
      label.append(title, input);
      return { label, input };
    };

    const createCompetitorRow = (item = {}) => {
      const row = document.createElement("div");
      row.className = "competitor-row";
      const rowId = `competitor-menu-${++rowCounter}`;
      const brandWrap = document.createElement("div");
      brandWrap.className = "supplier-field competitor-brand-field";
      const brandLabel = document.createElement("label");
      brandLabel.htmlFor = `${rowId}-brand`;
      brandLabel.textContent = labels.brandLabel;
      const picker = document.createElement("div");
      picker.className = "supplier-picker competitor-brand-picker";
      picker.dataset.brandPicker = "true";
      picker.dataset.addLabel = labels.addBrandLabel;
      picker.dataset.deleteBrandLabel = labels.deleteBrandLabel;
      const brandInput = document.createElement("input");
      brandInput.id = `${rowId}-brand`;
      brandInput.type = "text";
      brandInput.maxLength = 160;
      brandInput.value = item.brand || "";
      brandInput.placeholder = labels.brandLabel;
      brandInput.autocomplete = "off";
      brandInput.dataset.pickerInput = "";
      brandInput.setAttribute("role", "combobox");
      brandInput.setAttribute("aria-autocomplete", "list");
      brandInput.setAttribute("aria-controls", `${rowId}-list`);
      brandInput.setAttribute("aria-expanded", "false");
      const pickerToggle = document.createElement("button");
      pickerToggle.className = "supplier-picker-toggle";
      pickerToggle.type = "button";
      pickerToggle.textContent = "⌄";
      pickerToggle.setAttribute("aria-label", labels.brandLabel);
      pickerToggle.setAttribute("aria-controls", `${rowId}-list`);
      pickerToggle.setAttribute("aria-expanded", "false");
      const menu = document.createElement("div");
      menu.className = "supplier-menu";
      menu.id = `${rowId}-list`;
      menu.setAttribute("role", "listbox");
      menu.hidden = true;
      const noBrands = document.createElement("div");
      noBrands.className = "supplier-empty";
      noBrands.textContent = labels.emptyLabel;
      menu.append(noBrands);
      const addOption = document.createElement("button");
      addOption.className = "supplier-option supplier-add-option";
      addOption.type = "button";
      addOption.dataset.supplierAdd = "";
      addOption.hidden = true;
      menu.append(addOption);
      picker.append(brandInput, pickerToggle, menu);
      competitorBrands.forEach(brand => addPickerOption(picker, brand));
      brandWrap.append(brandLabel, picker);

      const price = makeField(labels.priceLabel, "competitor-price-field", "number", item.price, "0,00");
      price.input.type = "text";
      price.input.inputMode = "decimal";
      price.input.autocomplete = "off";
      const url = makeField(labels.linkLabel, "competitor-link-field", "text", item.url, "https://…");
      url.input.maxLength = 500;
      url.input.autocomplete = "url";
      const notes = makeField(labels.notesLabel, "competitor-notes-field", "text", item.notes, "");
      notes.input.maxLength = 300;
      const remove = document.createElement("button");
      remove.className = "competitor-remove";
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", labels.removeLabel);
      const difference = document.createElement("div");
      difference.className = "competitor-difference";
      difference.setAttribute("aria-live", "polite");
      const differenceText = document.createElement("span");
      const link = document.createElement("a");
      link.textContent = english ? "Open competitor link ↗" : "Ouvrir le lien concurrent ↗";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.hidden = true;
      difference.append(differenceText, link);
      row.append(brandWrap, price.label, url.label, notes.label, remove, difference);
      rowsContainer.append(row);
      initializeSearchablePicker(picker);

      const updateDifference = () => {
        const ownPrice = Number(saleInput?.value);
        const competitorPrice = parseLocalizedNumber(price.input.value);
        difference.classList.remove("competitor-cheaper", "competitor-pricier", "competitor-equal");
        if (!price.input.value || !Number.isFinite(ownPrice) || !Number.isFinite(competitorPrice)) {
          differenceText.textContent = "";
        } else {
          const differenceValue = competitorPrice - ownPrice;
          const brand = brandInput.value.trim() || labels.brandLabel;
          if (Math.abs(differenceValue) < 0.005) {
            differenceText.textContent = english ? `${brand} is the same price as yours.` : `${labels.differenceLabel} : ${brand} est au même prix.`;
            difference.classList.add("competitor-equal");
          } else if (differenceValue > 0) {
            differenceText.textContent = english
              ? `${brand} is ${formatCompetitorMoney(differenceValue)} more expensive.`
              : `${labels.differenceLabel} : ${brand} est ${formatCompetitorMoney(differenceValue)} plus cher.`;
            difference.classList.add("competitor-pricier");
          } else {
            differenceText.textContent = english
              ? `${brand} is ${formatCompetitorMoney(Math.abs(differenceValue))} cheaper.`
              : `${labels.differenceLabel} : ${brand} est ${formatCompetitorMoney(Math.abs(differenceValue))} moins cher.`;
            difference.classList.add("competitor-cheaper");
          }
        }
        const safeUrl = url.input.value.trim();
        if (/^https?:\/\//i.test(safeUrl)) {
          try {
            const parsed = new URL(safeUrl);
            link.href = parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "#";
            link.hidden = link.href === "#";
          } catch { link.hidden = true; }
        } else {
          link.hidden = true;
        }
      };
      [brandInput, price.input, url.input, notes.input].forEach(input => input.addEventListener("input", () => {
        updateDifference();
        syncCompetitors();
      }));
      remove.addEventListener("click", () => {
        row.remove();
        syncCompetitors();
      });
      updateDifference();
      return row;
    };

    syncCompetitors = () => {
      const rows = [...rowsContainer.querySelectorAll(".competitor-row")];
      const items = rows.map(row => ({
        brand: row.querySelector(".competitor-brand-picker [data-picker-input]").value.trim(),
        price: row.querySelector(".competitor-price-field input").value.trim(),
        url: row.querySelector(".competitor-link-field input").value.trim(),
        notes: row.querySelector(".competitor-notes-field input").value.trim(),
      })).filter(item => item.brand || item.price || item.url || item.notes);
      hiddenData.value = JSON.stringify(items);
      emptyMessage.hidden = rows.length > 0;
      addButton.disabled = rows.length >= 20;
    };

    let initialItems = [];
    try {
      initialItems = JSON.parse(document.querySelector("#competitor-initial-data")?.textContent || "[]");
    } catch { initialItems = []; }
    initialItems.forEach(createCompetitorRow);
    window.nombroLoadCompetitors = items => {
      rowsContainer.replaceChildren();
      (Array.isArray(items) ? items : []).slice(0, 20).forEach(item => {
        const row = createCompetitorRow(item);
        row.querySelectorAll("input").forEach(input => input.dispatchEvent(new Event("input", { bubbles: true })));
      });
      syncCompetitors();
    };
    addButton.addEventListener("click", () => {
      if (rowsContainer.querySelectorAll(".competitor-row").length >= 20) return;
      const row = createCompetitorRow();
      row.querySelector("[data-picker-input]").focus();
      syncCompetitors();
    });
    bulkButton?.addEventListener("click", () => {
      const entries = (bulkInput?.value || "").split(/\r?\n/).map(line => line.trim()).filter(Boolean);
      if (!entries.length) return;
      const available = Math.max(0, 20 - rowsContainer.querySelectorAll(".competitor-row").length);
      let added = 0;
      let skipped = 0;
      entries.forEach(line => {
        const [brand = "", price = "", url = "", notes = ""] = line.split(/[;\t]/).map(value => value.trim());
        if (!brand || !price || added >= available) {
          skipped += 1;
          return;
        }
        const row = createCompetitorRow({ brand, price: price.replace(",", "."), url, notes });
        row.querySelectorAll("input").forEach(input => input.dispatchEvent(new Event("input", { bubbles: true })));
        added += 1;
      });
      syncCompetitors();
      if (bulkStatus) {
        const addedText = competitionSection.dataset.bulkAdded || (english ? "competitor(s) added." : "concurrent(s) ajouté(s).");
        const limitText = competitionSection.dataset.bulkLimit || (english ? "The 20-competitor limit has been reached." : "La limite de 20 concurrents par produit est atteinte.");
        const skippedText = english ? "Some rows were skipped (invalid format or limit reached)." : "Certaines lignes ont été ignorées (format invalide ou limite atteinte).";
        bulkStatus.textContent = added
          ? `${added} ${addedText}${skipped ? ` ${skippedText}` : ""}`
          : available === 0 ? limitText : skippedText;
      }
      if (added) bulkInput.value = "";
    });
    productForm?.addEventListener("submit", syncCompetitors);
    saleInput?.addEventListener("input", () => {
      rowsContainer.querySelectorAll(".competitor-row").forEach(row => {
        row.querySelector(".competitor-price-field input").dispatchEvent(new Event("input"));
      });
    });
    syncCompetitors();
  }

  const photoInput = document.querySelector("#product-photo");
  const importFileInput = document.querySelector("#import-file");
  const importFileName = document.querySelector("#import-file-name");
  importFileInput?.addEventListener("change", () => {
    if (importFileName) {
      importFileName.textContent = importFileInput.files?.[0]?.name
        || (english ? "No file selected" : "Aucun fichier sélectionné");
    }
  });

  const photoDropzone = document.querySelector("#photo-dropzone");
  const photoPreview = document.querySelector("#photo-upload-preview");
  const photoPreviewImage = document.querySelector("#photo-upload-preview-image");
  const photoFileName = document.querySelector("#photo-file-name");
  const photoPreviewName = document.querySelector("#photo-preview-name");
  let selectedPhotoUrl = "";
  photoInput?.addEventListener("change", () => {
    if (selectedPhotoUrl) URL.revokeObjectURL(selectedPhotoUrl);
    selectedPhotoUrl = "";
    const file = photoInput.files?.[0];
    if (photoFileName) photoFileName.textContent = file?.name || (english ? "No file selected" : "Aucun fichier sélectionné");
    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    const allowedExtension = file && /\.(jpe?g|png|webp)$/i.test(file.name);
    if (!file || (!allowedTypes.includes(file.type) && !allowedExtension) || file.size > 5_000_000) {
      photoPreview.hidden = true;
      photoPreviewImage.removeAttribute("src");
      return;
    }
    selectedPhotoUrl = URL.createObjectURL(file);
    photoPreviewImage.src = selectedPhotoUrl;
    if (photoPreviewName) photoPreviewName.textContent = file.name;
    photoPreview.hidden = false;
  });
  photoDropzone?.addEventListener("dragover", event => {
    event.preventDefault();
    photoDropzone.classList.add("is-dragging");
  });
  photoDropzone?.addEventListener("dragleave", event => {
    if (!photoDropzone.contains(event.relatedTarget)) photoDropzone.classList.remove("is-dragging");
  });
  photoDropzone?.addEventListener("drop", event => {
    event.preventDefault();
    photoDropzone.classList.remove("is-dragging");
    const file = event.dataTransfer?.files?.[0];
    if (!file || !photoInput) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    photoInput.files = transfer.files;
    photoInput.dispatchEvent(new Event("change", { bubbles: true }));
  });

  const languageSelect = document.querySelector("#language-select");
  const languageStatus = document.querySelector("#language-save-status");
  languageSelect?.addEventListener("change", async () => {
    const previous = document.querySelector('meta[name="language"]').content;
    languageStatus.textContent = language === "en" ? "Saving…" : "Enregistrement…";
    try {
      const response = await fetch("/api/preferences/langue", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
        },
        body: JSON.stringify({ language: languageSelect.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not save language.");
      const profileForm = document.querySelector(".settings-form");
      const draft = profileForm ? Object.fromEntries(new FormData(profileForm)) : {};
      sessionStorage.setItem("nombro-profile-draft", JSON.stringify(draft));
      window.location.reload();
    } catch (error) {
      languageSelect.value = previous;
      languageStatus.textContent = error.message || (language === "en" ? "Could not save language." : "Impossible d’enregistrer la langue.");
    }
  });
  const savedProfileDraft = sessionStorage.getItem("nombro-profile-draft");
  if (savedProfileDraft) {
    try {
      const draft = JSON.parse(savedProfileDraft);
      const profileForm = document.querySelector(".settings-form");
      for (const [name, value] of Object.entries(draft)) {
        const field = profileForm?.elements.namedItem(name);
        if (field && name !== "csrf_token" && name !== "language" && name !== "theme") field.value = value;
      }
    } catch { /* Ignore an invalid local profile draft. */ }
    sessionStorage.removeItem("nombro-profile-draft");
  }

  const themeSelect = document.querySelector("#theme-select");
  const themeStatus = document.querySelector("#theme-save-status");
  themeSelect?.addEventListener("change", async () => {
    const previous = [...document.body.classList].find(name => name.startsWith("theme-")) || "theme-light";
    const next = `theme-${themeSelect.value}`;
    document.body.classList.remove("theme-light", "theme-dark", "theme-green-dark", "theme-black-dark", "theme-colorful", "theme-cyberpunk");
    document.body.classList.add(next);
    themeStatus.textContent = language === "en" ? "Saving…" : "Enregistrement…";
    try {
      const response = await fetch("/api/preferences/theme", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
        },
        body: JSON.stringify({ theme: themeSelect.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || (english ? "Could not save theme." : "Impossible d’enregistrer le thème."));
      themeStatus.textContent = language === "en" ? "Saved automatically." : "Enregistré automatiquement.";
    } catch (error) {
      document.body.classList.remove("theme-light", "theme-dark", "theme-green-dark", "theme-black-dark", "theme-colorful", "theme-cyberpunk");
      document.body.classList.add(previous);
      themeSelect.value = previous.replace("theme-", "");
      themeStatus.textContent = error.message || (language === "en" ? "Could not save theme." : "Erreur lors de l’enregistrement.");
    }
  });

  const format = (value, digits = 2) => new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number.isFinite(value) ? value : 0);
  let currency = document.querySelector("#currency-select")?.value
    || document.querySelector('meta[name="currency-code"]')?.content
    || "EUR";
  const formatMoney = value => new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);

  const productRows = document.querySelector("#product-rows");
  const search = document.querySelector("#product-search");
  const filter = document.querySelector("#product-filter");
  const supplierFilter = document.querySelector("#supplier-filter");
  const targetFilter = document.querySelector("#target-filter");
  const marginMinFilter = document.querySelector("#margin-min-filter");
  const marginMaxFilter = document.querySelector("#margin-max-filter");
  const sort = document.querySelector("#product-sort");
  let refreshGridView = () => {};

  if (productRows && search && filter) {
    const allRows = [...productRows.querySelectorAll(".product-row")];
    const filterRows = () => {
      const query = search.value.trim().toLocaleLowerCase("fr");
      const status = filter.value;
      const supplier = supplierFilter?.value || "all";
      const target = targetFilter?.value || "all";
      const minMargin = marginMinFilter?.value === "" ? -Infinity : Number(marginMinFilter.value);
      const maxMargin = marginMaxFilter?.value === "" ? Infinity : Number(marginMaxFilter.value);
      const mode = sort?.value || "recent";
      const sorted = [...allRows].sort((a, b) => {
        if (mode === "name") return a.dataset.name.localeCompare(b.dataset.name, "fr");
        if (mode === "profit-desc") return Number(b.dataset.marginTotal) - Number(a.dataset.marginTotal);
        if (mode === "margin-desc") return Number(b.dataset.margin) - Number(a.dataset.margin);
        return Number(a.dataset.order) - Number(b.dataset.order);
      });
      sorted.forEach((row, index) => {
        row.querySelector(".index-cell").textContent = String(index + 1);
        row.hidden = !row.dataset.name.includes(query)
          || (status !== "all" && row.dataset.status !== status)
          || (supplier !== "all" && row.dataset.supplier !== supplier)
          || (target === "below" && row.dataset.belowTarget !== "yes")
          || Number(row.dataset.margin) < minMargin
          || Number(row.dataset.margin) > maxMargin;
        productRows.appendChild(row);
      });
      const visible = sorted.filter(row => !row.hidden).length;
      document.querySelector("#result-count").textContent = `${visible} ${english ? (visible === 1 ? "row" : "rows") : `ligne${visible === 1 ? "" : "s"}`}`;
      document.querySelector("#no-results").hidden = visible !== 0;
    };
    refreshGridView = filterRows;
    search.addEventListener("input", filterRows);
    filter.addEventListener("change", filterRows);
    supplierFilter?.addEventListener("change", filterRows);
    targetFilter?.addEventListener("change", filterRows);
    marginMinFilter?.addEventListener("input", filterRows);
    marginMaxFilter?.addEventListener("input", filterRows);
    sort?.addEventListener("change", filterRows);
  }

  const currencySelect = document.querySelector("#currency-select");
  currencySelect?.addEventListener("change", async () => {
    const previous = currency;
    const message = document.querySelector("#save-message");
    message.textContent = english ? "Updating currency…" : "Mise à jour de la devise…";
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
      if (!response.ok) throw new Error(result.error || (english ? "Could not save currency." : "Impossible d’enregistrer la devise."));
      currency = result.currency;
      document.querySelectorAll(".currency-label").forEach(label => { label.textContent = currency; });
      productRows?.querySelectorAll(".product-row").forEach(calculateRow);
      message.textContent = english ? `Currency ${currency} saved · no conversion applied` : `Devise ${currency} enregistrée · aucune conversion appliquée`;
    } catch (error) {
      currencySelect.value = previous;
      message.textContent = error.message || (english ? "Could not save currency." : "Erreur lors de l’enregistrement de la devise");
    }
  });

  const money = document.querySelector("#summary-margin-total");
  const updateSummary = () => {
    if (!productRows) return;
    const rows = [...productRows.querySelectorAll(".product-row")];
    const totalMargin = rows.reduce((sum, row) => sum + Number(row.dataset.marginTotal || 0), 0);
    const profitable = rows.filter(row => row.dataset.status === "profit").length;
    const margins = rows.map(row => Number(row.dataset.margin || 0));
    const average = margins.length ? margins.reduce((sum, value) => sum + value, 0) / margins.length : 0;
    if (money) money.textContent = formatMoney(totalMargin);
    const profitableNode = document.querySelector("#summary-profitable");
    const marginNode = document.querySelector("#summary-margin");
    if (profitableNode) profitableNode.textContent = String(profitable);
    if (marginNode) marginNode.textContent = format(average, 1);
  };

  const fitSpreadsheetInput = input => {
    if (input.hasAttribute("data-fit-full-column")) {
      input.style.removeProperty("width");
      return;
    }
    const valueLength = (input.value || input.placeholder || "").trim().length;
    const field = input.dataset.field;
    const minimum = field === "barcode" ? 10 : field === "supplier" ? 8 : 5;
    const maximum = field === "barcode" ? 24 : 22;
    const extra = input.type === "number" ? 3 : 2;
    const characters = Math.min(maximum, Math.max(minimum, valueLength + extra));
    input.style.width = `${characters}ch`;
  };
  productRows?.querySelectorAll("[data-field]").forEach(fitSpreadsheetInput);

  const calculateRow = (row, editedField = "") => {
    const value = field => Number(row.querySelector(`[data-field="${field}"]`).value) || 0;
    let purchase = value("purchase_ht");
    let sale = value("sale_ht");
    const vat = value("vat_rate");
    const extra = value("extra_cost_ht");
    const quantity = Math.max(1, value("quantity"));
    const factor = 1 + vat / 100;
    const purchaseTtcInput = row.querySelector('[data-field="purchase_ttc"]');
    const saleTtcInput = row.querySelector('[data-field="sale_ttc"]');
    const purchaseTtc = editedField === "purchase_ttc" ? value("purchase_ttc") : purchase * factor;
    const saleTtc = editedField === "sale_ttc" ? value("sale_ttc") : sale * factor;
    if (editedField === "purchase_ttc") {
      purchase = factor ? purchaseTtc / factor : purchaseTtc;
      row.querySelector('[data-field="purchase_ht"]').value = purchase.toFixed(2);
    } else {
      purchaseTtcInput.value = purchaseTtc.toFixed(2);
    }
    if (editedField === "sale_ttc") {
      sale = factor ? saleTtc / factor : saleTtc;
      row.querySelector('[data-field="sale_ht"]').value = sale.toFixed(2);
    } else {
      saleTtcInput.value = saleTtc.toFixed(2);
    }
    const marginValue = sale - purchase;
    const marginTotal = marginValue * quantity;
    const margin = sale ? marginValue / sale * 100 : 0;
    const coefficient = purchase ? (sale * factor) / purchase : 0;
    row.dataset.name = [
      row.querySelector(".name-cell").textContent,
      ...["product_code", "barcode", "supplier", "service_cost_ttc"].map(field => row.querySelector(`[data-field="${field}"]`).value),
    ].join(" ").toLocaleLowerCase("fr");
    row.dataset.supplier = row.querySelector('[data-field="supplier"]').value.trim().toLocaleLowerCase("fr");
    const outputs = {
      extra_ttc: formatMoney(extra * factor),
      margin_value: formatMoney(marginValue),
      margin_total: formatMoney(marginTotal),
      margin: `${format(margin, 1)} %`,
      coefficient: format(coefficient),
    };
    for (const [key, text] of Object.entries(outputs)) {
      row.querySelector(`[data-output="${key}"]`).textContent = text;
    }
    const loss = marginValue < 0;
    row.querySelector(".purchase-ttc-cell").classList.toggle("loss-cell", loss);
    row.querySelector('[data-output="margin_value"]').classList.toggle("loss-cell", loss);
    row.querySelector('[data-output="margin_total"]').classList.toggle("loss-cell", loss);
    row.querySelector('[data-output="margin"]').classList.toggle("loss-cell", loss);
    const status = marginValue > 0 ? "profit" : loss ? "loss" : "even";
    row.dataset.marginTotal = String(marginTotal);
    row.dataset.margin = String(margin);
    row.dataset.status = status;
    row.dataset.belowTarget = margin < Number(row.dataset.targetPercent || 0) ? "yes" : "no";
    const badge = row.querySelector('[data-output="status"]');
    badge.textContent = status === "profit" ? (english ? "Profitable" : "Rentable") : status === "loss" ? (english ? "At a loss" : "À perte") : (english ? "Break-even" : "Équilibre");
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
    message.textContent = english ? "Saving…" : "Enregistrement…";
    const rowId = row.dataset.id;
    const getRowData = () => Object.fromEntries([...row.querySelectorAll("[data-field]")]
      .map(input => [input.dataset.field, input.value]));
    try {
      do {
        row.dataset.saveAgain = "false";
        const data = getRowData();
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
          throw new Error(result.error || (english ? "Could not save changes." : "Enregistrement impossible."));
        }
        const result = await response.json();
        if (!result.saved) throw new Error(english ? "The server did not confirm the save." : "Le serveur n’a pas confirmé l’enregistrement.");
      } while (row.dataset.saveAgain === "true");
      const pending = readPendingGrid();
      delete pending[rowId];
      writePendingGrid(pending);
      message.textContent = english ? "All changes are saved" : "Toutes les modifications sont enregistrées";
      statusCell.classList.remove("is-saving", "save-error", "is-pending");
      statusCell.classList.add("is-saved");
      refreshGridView();
      window.setTimeout(() => statusCell.classList.remove("is-saved"), 1200);
    } catch (error) {
      if (!navigator.onLine || error instanceof TypeError) {
        const pending = readPendingGrid();
        pending[rowId] = { fields: getRowData(), savedAt: Date.now() };
        writePendingGrid(pending);
        message.textContent = english ? "Offline change saved on this device; waiting to sync." : "Modification gardée sur cet appareil, en attente de synchronisation.";
        statusCell.classList.remove("is-saving", "save-error");
        statusCell.classList.add("is-pending");
        updateOfflineBanner();
      } else {
        message.textContent = error.message || (english ? "Could not save changes." : "Erreur lors de l’enregistrement");
        statusCell.classList.remove("is-saving");
        statusCell.classList.add("save-error");
      }
    } finally {
      row.dataset.saving = "false";
    }
  };

  const syncPendingGrid = async () => {
    if (!navigator.onLine) return;
    const pending = readPendingGrid();
    const ids = Object.keys(pending);
    if (!ids.length) {
      updateOfflineBanner();
      return;
    }
    updateOfflineBanner(english ? `Sending ${ids.length} pending change(s)…` : `Envoi de ${ids.length} modification(s) en attente…`);
    for (const id of ids) {
      const row = document.querySelector(`.product-row[data-id="${CSS.escape(id)}"]`);
      if (row?.dataset.saving === "true") continue;
      try {
        const response = await fetch(`/api/produit/${encodeURIComponent(id)}/cellules`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]')?.content || "",
          },
          credentials: "same-origin",
          body: JSON.stringify(pending[id].fields),
        });
        const result = await response.json();
        if (!response.ok || !result.saved) throw new Error(result.error || "Sync failed");
        const current = readPendingGrid();
        if (current[id]?.savedAt === pending[id]?.savedAt) delete current[id];
        writePendingGrid(current);
        row?.querySelector(".status-cell")?.classList.remove("is-pending", "save-error");
      } catch {
        updateOfflineBanner(english
          ? "Some changes are still waiting. Reconnect to Nombro and try again."
          : "Des changements restent en attente. Reconnecte-toi à Nombro pour réessayer.");
        return;
      }
    }
    const remaining = Object.keys(readPendingGrid()).length;
    if (!remaining) {
      const message = document.querySelector("#save-message");
      if (message) message.textContent = english ? "All changes are saved" : "Toutes les modifications sont enregistrées";
      updateOfflineBanner(english ? "All pending changes have been sent." : "Toutes les modifications en attente ont été envoyées.");
      window.setTimeout(() => updateOfflineBanner(), 3500);
    }
  };
  window.addEventListener("online", syncPendingGrid);
  window.setInterval(() => {
    if (navigator.onLine) syncPendingGrid();
  }, 15000);
  if (navigator.onLine) syncPendingGrid();

  productRows?.querySelectorAll(".product-row").forEach(row => {
    row.querySelectorAll("[data-field]").forEach(input => {
      input.addEventListener("input", () => {
        fitSpreadsheetInput(input);
        calculateRow(row, input.dataset.field);
        document.querySelector("#save-message").textContent = english ? "Value changed · leave the cell to save" : "Valeur modifiée · quitte la cellule pour enregistrer";
      });
      input.addEventListener("change", () => saveRow(row));
      if (input.dataset.field === "supplier") {
        input.addEventListener("change", () => {
          const supplier = input.value.trim();
          if (!supplier) return;
          const normalized = supplier.toLocaleLowerCase("fr");
          const suggestions = document.querySelector("#supplier-options");
          if (suggestions && ![...suggestions.options].some(option => option.value.toLocaleLowerCase("fr") === normalized)) {
            suggestions.append(new Option(supplier, supplier));
          }
          if (supplierFilter && ![...supplierFilter.options].some(option => option.value === normalized)) {
            supplierFilter.append(new Option(supplier, normalized));
          }
        });
      }
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
    const catalogQuery = document.querySelector("#catalog-product-query");
    const catalogResults = document.querySelector("#catalog-product-results");
    const catalogStatus = document.querySelector("#catalog-product-status");
    let catalogSearchTimer = 0;
    let catalogSearchController = null;
    const hideCatalogResults = () => {
      if (!catalogResults) return;
      catalogResults.hidden = true;
      catalogQuery?.setAttribute("aria-expanded", "false");
    };
    const renderCatalogResults = products => {
      if (!catalogResults || !catalogQuery) return;
      catalogResults.replaceChildren();
      if (!products.length) {
        const empty = document.createElement("div");
        empty.className = "catalog-search-empty";
        empty.textContent = english ? "No matching product in your Nombro catalog." : "Aucun produit correspondant dans ton catalogue Nombro.";
        catalogResults.append(empty);
      } else {
        products.forEach(product => {
          const option = document.createElement("button");
          option.type = "button";
          option.className = "catalog-product-option";
          option.setAttribute("role", "option");
          const name = document.createElement("strong");
          name.textContent = product.name;
          const meta = document.createElement("small");
          meta.textContent = [product.manufacturer, product.supplier_ref, product.supplier]
            .filter(Boolean).join(" · ");
          const price = document.createElement("span");
          price.textContent = `${english ? "Purchase" : "Achat"} : ${formatMoney(Number(product.purchase_ttc) || 0)} · ${product.competitors?.length || 0} ${english ? "competitor(s)" : "concurrent(s)"}`;
          option.append(name, meta, price);
          option.addEventListener("click", () => {
            const fields = {
              name: product.name,
              product_code: product.product_code,
              manufacturer: product.manufacturer,
              supplier_ref: product.supplier_ref,
              supplier: product.supplier,
              purchase_ttc: product.purchase_ttc,
              sale_ttc: product.sale_ttc,
              vat_rate: product.vat_rate,
              extra_cost_ttc: product.extra_cost_ttc,
              service_cost_ttc: product.service_cost_ttc,
              quantity: 1,
              notes: "",
            };
            for (const [name, value] of Object.entries(fields)) {
              const field = priceForm.elements.namedItem(name);
              if (!field) continue;
              field.value = value ?? "";
              field.dispatchEvent(new Event("input", { bubbles: true }));
            }
            const barcode = priceForm.elements.namedItem("barcode");
            if (barcode) barcode.value = "";
            window.nombroLoadCompetitors?.(product.competitors || []);
            catalogQuery.value = product.name;
            catalogStatus.textContent = english
              ? "Saved details loaded. Confirm current supplier prices before saving this new line."
              : "Fiche enregistrée recopiée. Vérifie les prix actuels chez le fournisseur avant d’enregistrer cette nouvelle ligne.";
            hideCatalogResults();
          });
          catalogResults.append(option);
        });
      }
      catalogResults.hidden = false;
      catalogQuery.setAttribute("aria-expanded", "true");
    };
    catalogQuery?.addEventListener("input", () => {
      window.clearTimeout(catalogSearchTimer);
      catalogSearchController?.abort();
      const query = catalogQuery.value.trim();
      if (query.length < 2) {
        hideCatalogResults();
        return;
      }
      catalogSearchTimer = window.setTimeout(async () => {
        catalogSearchController = new AbortController();
        try {
          const response = await fetch(`/api/produits/recherche?q=${encodeURIComponent(query)}`, {
            credentials: "same-origin", signal: catalogSearchController.signal,
          });
          if (!response.ok) throw new Error("search failed");
          const result = await response.json();
          renderCatalogResults(result.products || []);
        } catch (error) {
          if (error.name !== "AbortError" && catalogStatus) {
            catalogStatus.textContent = english ? "Catalog search is temporarily unavailable." : "La recherche dans le catalogue est momentanément indisponible.";
          }
        }
      }, 220);
    });
    catalogQuery?.addEventListener("keydown", event => {
      if (event.key === "Escape") hideCatalogResults();
    });
    document.addEventListener("pointerdown", event => {
      if (catalogResults && !catalogResults.contains(event.target) && event.target !== catalogQuery) hideCatalogResults();
    });
    const queueKey = `nombro-pending:${location.pathname}`;
    const queueStatus = document.createElement("p");
    queueStatus.className = "client-sync-status";
    queueStatus.setAttribute("role", "status");
    queueStatus.setAttribute("aria-live", "polite");
    priceForm.append(queueStatus);
    let sendingQueuedProduct = false;
    let livePhoto = null;
    const readQueuedProduct = () => {
      try { return JSON.parse(localStorage.getItem(queueKey) || "null"); }
      catch { return null; }
    };
    const sendQueuedProduct = async () => {
      const queued = readQueuedProduct();
      if (!queued || sendingQueuedProduct) return;
      if (!navigator.onLine) {
        queueStatus.textContent = english
          ? "Saved on this computer. It will be sent automatically when the network returns."
          : "Fiche gardée sur cet ordinateur. Elle sera envoyée automatiquement au retour du réseau.";
        updateOfflineBanner();
        return;
      }
      sendingQueuedProduct = true;
      queueStatus.textContent = english ? "Sending saved product to the server…" : "Envoi de la fiche enregistrée au serveur…";
      const formData = new FormData();
      for (const [name, value] of queued.fields) {
        formData.append(name, name === "csrf_token"
          ? (priceForm.querySelector('[name="csrf_token"]')?.value || value)
          : value);
      }
      if (livePhoto) formData.append("photo", livePhoto);
      try {
        const response = await fetch(priceForm.action, { method: "POST", body: formData, credentials: "same-origin" });
        if (response.url.endsWith("/grille")) {
          localStorage.removeItem(queueKey);
          livePhoto = null;
          location.assign(response.url);
          return;
        }
        queueStatus.textContent = english
          ? "The server did not accept the product. Check the form; it remains saved in this browser."
          : "Le serveur n’a pas accepté la fiche. Vérifie le formulaire ; elle reste enregistrée dans ce navigateur.";
      } catch {
        queueStatus.textContent = english
          ? "Saved on this computer. It will be sent automatically when the server is reachable."
          : "Fiche gardée sur cet ordinateur. Elle sera envoyée automatiquement dès que le serveur sera joignable.";
      } finally {
        sendingQueuedProduct = false;
      }
    };
    priceForm.addEventListener("submit", event => {
      event.preventDefault();
      if (!priceForm.reportValidity()) return;
      const fields = [...new FormData(priceForm).entries()]
        .filter(([name, value]) => !(value instanceof File))
        .map(([name, value]) => [name, String(value)]);
      localStorage.setItem(queueKey, JSON.stringify({ fields, savedAt: Date.now() }));
      livePhoto = priceForm.querySelector('input[type="file"][name="photo"]')?.files?.[0] || null;
      sendQueuedProduct();
    });
    window.addEventListener("online", sendQueuedProduct);
    window.setInterval(() => {
      if (navigator.onLine) sendQueuedProduct();
    }, 15000);
    if (readQueuedProduct()) sendQueuedProduct();

    const input = name => priceForm.elements.namedItem(name);
    const refresh = () => {
      const purchase = Number(input("purchase_ttc").value) || 0;
      const sale = Number(input("sale_ttc").value) || 0;
      const vat = Number(input("vat_rate").value) || 0;
      const quantity = Number(input("quantity").value) || 1;
      const factor = 1 + vat / 100;
      const purchaseHt = purchase / factor;
      const saleHt = sale / factor;
      const marginValue = saleHt - purchaseHt;
      const marginTotal = marginValue * quantity;
      const margin = saleHt ? marginValue / saleHt * 100 : 0;
      const coefficient = purchaseHt ? sale / purchaseHt : 0;
      document.querySelector("#preview-sale-ht").textContent = formatMoney(sale / factor);
      document.querySelector("#preview-cost-ht").textContent = formatMoney(purchaseHt);
      document.querySelector("#preview-margin-total").textContent = formatMoney(marginTotal);
      document.querySelector("#preview-margin").textContent = `${format(margin)} %`;
      document.querySelector("#preview-coefficient").textContent = format(coefficient);
      document.querySelector("#preview-margin-total").classList.toggle("negative", marginTotal < 0);
    };
    priceForm.addEventListener("input", refresh);
    refresh();

    const barcodeInput = input("barcode");
    const barcodeNotice = document.querySelector("#barcode-notice");
    let barcodeTimer;
    barcodeInput?.addEventListener("input", () => {
      clearTimeout(barcodeTimer);
      barcodeNotice.textContent = "";
      const barcode = barcodeInput.value.trim();
      if (!barcode) return;
      barcodeTimer = setTimeout(async () => {
        const params = new URLSearchParams({ barcode });
        const productId = priceForm.dataset.productId;
        if (productId) params.set("exclude", productId);
        try {
          const response = await fetch(`/api/code-barres/verifier?${params}`);
          const result = await response.json();
          barcodeNotice.textContent = result.duplicate
            ? (english ? `Barcode already used by “${result.name}”.` : `Code déjà utilisé par « ${result.name} ».`)
            : (english ? "Barcode available." : "Code disponible.");
          barcodeNotice.classList.toggle("barcode-conflict", result.duplicate);
        } catch {
          barcodeNotice.textContent = english ? "Barcode check is temporarily unavailable." : "Vérification momentanément indisponible.";
        }
      }, 300);
    });
    if (barcodeInput?.value.trim()) barcodeInput.dispatchEvent(new Event("input", { bubbles: true }));
  }
});

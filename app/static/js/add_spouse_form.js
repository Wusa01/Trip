document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupNewSpouseForm();
  setupExistingSpousePicker();
});


// ---------------------------------------------------------------------------
// التبديل بين التبويبين
// ---------------------------------------------------------------------------

function setupTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  const panels = { new: document.getElementById("tab-new"), existing: document.getElementById("tab-existing") };

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      Object.entries(panels).forEach(([key, el]) => { el.hidden = key !== btn.dataset.tab; });
    });
  });
}


// ---------------------------------------------------------------------------
// تبويب: شخص جديد
// ---------------------------------------------------------------------------

function setupNewSpouseForm() {
  const childrenRows = document.getElementById("children-rows");
  const childTemplate = document.getElementById("child-row-template");

  document.getElementById("add-child-btn").addEventListener("click", () => {
    const node = childTemplate.content.cloneNode(true);
    const row = node.querySelector(".child-row");
    row.querySelector(".remove-child-btn").addEventListener("click", () => row.remove());
    childrenRows.appendChild(row);
  });

  document.getElementById("new-spouse-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.getElementById("new-form-error");
    errorBox.hidden = true;

    const payload = {
      full_name: document.getElementById("spouse_name").value.trim(),
      tribe_name: document.getElementById("spouse_tribe").value.trim() || null,
      children: [...childrenRows.querySelectorAll(".child-row")].map(row => ({
        full_name: row.querySelector(".child-name").value.trim(),
        gender: row.querySelector(".child-gender").value,
      })).filter(c => c.full_name),
    };

    try {
      const res = await fetch(`/persons/api/${TARGET_PERSON_ID}/add-spouse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok) {
        errorBox.textContent = data.error || "حدث خطأ غير متوقع";
        errorBox.hidden = false;
        return;
      }

      window.location.href = `/persons/${TARGET_PERSON_ID}`;
    } catch (err) {
      errorBox.textContent = "تعذّر الاتصال بالخادم";
      errorBox.hidden = false;
    }
  });
}


// ---------------------------------------------------------------------------
// تبويب: شخص مسجَّل مسبقاً
// ---------------------------------------------------------------------------

function setupExistingSpousePicker() {
  const input = document.getElementById("existing-spouse-input");
  const resultsBox = document.getElementById("existing-spouse-results");
  const hiddenInput = document.getElementById("existing-spouse-id");
  const confirmBox = document.getElementById("existing-spouse-confirm");
  const warningBox = document.getElementById("existing-spouse-warning");
  let debounceTimer = null;
  let currentResults = [];

  function closeDropdown() {
    resultsBox.hidden = true;
    resultsBox.innerHTML = "";
  }

  function selectItem(item) {
    input.value = item.full_name;
    hiddenInput.value = item.id;
    closeDropdown();

    confirmBox.textContent = `✓ تم اختيار: ${item.full_name} (${item.public_id})${item.tribe ? " — " + item.tribe : ""}`;
    confirmBox.hidden = false;

    if (item.marital_status === "married") {
      warningBox.textContent = `تنبيه: ${item.full_name} مسجَّل بالفعل بحالة "متزوج" — هذا سيضيف زواجاً إضافياً له (تعدد مسموح)، وليس استبدالاً.`;
      warningBox.hidden = false;
    } else {
      warningBox.hidden = true;
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    hiddenInput.value = "";
    confirmBox.hidden = true;
    warningBox.hidden = true;
    const query = input.value.trim();

    if (query.length < 2) { closeDropdown(); return; }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/persons/api/search-for-spouse?q=${encodeURIComponent(query)}&for_person_id=${TARGET_PERSON_ID}`);
        const results = await res.json();
        currentResults = results;

        if (!results.length) {
          resultsBox.innerHTML = `<div class="picker-empty muted small">لا توجد نتائج مطابقة (يظهر فقط الجنس المعاكس)</div>`;
          resultsBox.hidden = false;
          return;
        }

        resultsBox.innerHTML = `<div class="results-list">` + results.map((r, idx) => `
          <div class="result-row picker-result-row" data-idx="${idx}">
            <div class="result-main">
              <div class="result-name">${r.full_name}</div>
              <div class="muted small">${r.public_id}${r.tribe ? " — " + r.tribe : ""}</div>
            </div>
          </div>`).join("") + `</div>`;
        resultsBox.hidden = false;

        resultsBox.querySelectorAll(".picker-result-row").forEach(row => {
          row.addEventListener("click", () => selectItem(currentResults[parseInt(row.dataset.idx, 10)]));
        });
      } catch (e) {
        closeDropdown();
      }
    }, 250);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!resultsBox.hidden && currentResults.length > 0) selectItem(currentResults[0]);
    }
  });

  document.addEventListener("click", (e) => {
    if (!resultsBox.contains(e.target) && e.target !== input) closeDropdown();
  });

  document.getElementById("link-existing-btn").addEventListener("click", async () => {
    const errorBox = document.getElementById("existing-form-error");
    errorBox.hidden = true;

    const spouseId = hiddenInput.value;
    if (!spouseId) {
      errorBox.textContent = "الرجاء اختيار الشخص من نتائج البحث أولاً";
      errorBox.hidden = false;
      return;
    }

    const formData = new FormData();
    formData.append("spouse_id", spouseId);
    const marriageDate = document.getElementById("marriage_date").value;
    if (marriageDate) formData.append("marriage_date", marriageDate);

    try {
      const res = await fetch(`/persons/api/${TARGET_PERSON_ID}/link-spouse`, { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        errorBox.textContent = data.error || "تعذّر الربط";
        errorBox.hidden = false;
        return;
      }

      window.location.href = `/persons/${TARGET_PERSON_ID}`;
    } catch (e) {
      errorBox.textContent = "تعذّر الاتصال بالخادم";
      errorBox.hidden = false;
    }
  });
}

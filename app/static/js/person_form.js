document.addEventListener("DOMContentLoaded", () => {
  const genderSelect = document.getElementById("gender");
  const maritalSelect = document.getElementById("marital_status");

  const spousesSection = document.getElementById("spouses-section");
  const spousesTitle = document.getElementById("spouses-title");
  const spousesRows = document.getElementById("spouses-rows");
  const addSpouseBtn = document.getElementById("add-spouse-btn");

  const exSpouseSection = document.getElementById("ex-spouse-section");
  const exSpouseTitle = document.getElementById("ex-spouse-title");
  const exSpouseRow = document.getElementById("ex-spouse-row");

  const spouseTemplate = document.getElementById("spouse-row-template");
  const childTemplate = document.getElementById("child-row-template");

  // -------------------------------------------------------------------
  // إظهار/إخفاء الأقسام حسب الحالة الاجتماعية — "أعزب" لا يُظهر أي تبويب
  // -------------------------------------------------------------------
  function updateVisibility() {
    const status = maritalSelect.value;
    const gender = genderSelect.value;

    spousesSection.hidden = status !== "married";
    exSpouseSection.hidden = status !== "divorced";

    spousesTitle.textContent = gender === "female" ? "الزوج" : "الزوجات";
    exSpouseTitle.textContent = gender === "female" ? "الزوج السابق" : "الزوجة السابقة";

    if (status === "married" && spousesRows.children.length === 0) {
      addSpouseRow();
    }
    if (status === "married" && gender === "female") {
      addSpouseBtn.hidden = spousesRows.children.length >= 1; // المرأة: زوج واحد فقط
    } else {
      addSpouseBtn.hidden = status !== "married";
    }

    if (status === "divorced" && exSpouseRow.children.length === 0) {
      exSpouseRow.appendChild(buildSpouseBlock());
    }
  }

  genderSelect.addEventListener("change", updateVisibility);
  maritalSelect.addEventListener("change", updateVisibility);

  // -------------------------------------------------------------------
  // بناء صف زوجة/زوج + قدرته على إضافة أبناء خاصين به
  // -------------------------------------------------------------------
  function buildSpouseBlock() {
    const node = spouseTemplate.content.cloneNode(true);
    const block = node.querySelector(".spouse-block");

    block.querySelector(".remove-spouse-btn").addEventListener("click", () => {
      block.remove();
      updateVisibility();
    });

    block.querySelector(".add-child-btn").addEventListener("click", () => {
      const childrenList = block.querySelector(".children-list");
      const childNode = childTemplate.content.cloneNode(true);
      const childRow = childNode.querySelector(".child-row");
      childRow.querySelector(".remove-child-btn").addEventListener("click", () => childRow.remove());
      childrenList.appendChild(childRow);
    });

    return block;
  }

  function addSpouseRow() {
    spousesRows.appendChild(buildSpouseBlock());
    updateVisibility();
  }

  addSpouseBtn.addEventListener("click", addSpouseRow);

  // -------------------------------------------------------------------
  // تجميع بيانات صف زوجة واحد (اسمها، عشيرتها، أبناؤها)
  // -------------------------------------------------------------------
  function collectSpouseBlock(block) {
    return {
      full_name: block.querySelector(".spouse-name").value.trim(),
      tribe_name: block.querySelector(".spouse-tribe").value.trim() || null,
      children: [...block.querySelectorAll(".child-row")].map(row => ({
        full_name: row.querySelector(".child-name").value.trim(),
        gender: row.querySelector(".child-gender").value,
      })).filter(c => c.full_name),
    };
  }

  // -------------------------------------------------------------------
  // الإرسال
  // -------------------------------------------------------------------
  document.getElementById("person-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.getElementById("form-error");
    errorBox.hidden = true;

    const payload = {
      full_name: document.getElementById("full_name").value.trim(),
      gender: genderSelect.value,
      tribe_name: document.getElementById("tribe_name").value.trim() || null,
      disambiguation_note: document.getElementById("disambiguation_note").value || null,
      marital_status: maritalSelect.value,
      is_living: document.getElementById("is_living").value === "true",
      notes: document.getElementById("notes").value || null,
      spouses: maritalSelect.value === "married"
        ? [...spousesRows.querySelectorAll(".spouse-block")].map(collectSpouseBlock).filter(s => s.full_name)
        : [],
      ex_spouse: maritalSelect.value === "divorced" && exSpouseRow.firstElementChild
        ? collectSpouseBlock(exSpouseRow.firstElementChild)
        : null,
    };

    try {
      const res = await fetch("/persons/api/create-full", {
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

      window.location.href = `/persons/${data.id}`;
    } catch (err) {
      errorBox.textContent = "تعذّر الاتصال بالخادم";
      errorBox.hidden = false;
    }
  });

  updateVisibility();
});

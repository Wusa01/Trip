document.addEventListener("DOMContentLoaded", () => {
  setupPersonForm();
  loadFamilyManagement();
});


// ---------------------------------------------------------------------------
// حفظ البيانات الشخصية
// ---------------------------------------------------------------------------

function setupPersonForm() {
  const form = document.getElementById("edit-person-form");
  const errorBox = document.getElementById("form-error");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.hidden = true;

    const formData = new FormData(form);

    try {
      const res = await fetch(`/persons/api/${EDIT_PERSON_ID}/update`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (!res.ok) {
        errorBox.textContent = data.error || "حدث خطأ غير متوقع";
        errorBox.hidden = false;
        return;
      }

      window.location.href = `/persons/${EDIT_PERSON_ID}`;
    } catch (err) {
      errorBox.textContent = "تعذّر الاتصال بالخادم";
      errorBox.hidden = false;
    }
  });
}


// ---------------------------------------------------------------------------
// إدارة الزوجات والأبناء + الوالدين
// ---------------------------------------------------------------------------

async function loadFamilyManagement() {
  const spousesBox = document.getElementById("spouses-manage-box");
  const parentsBox = document.getElementById("parents-manage-box");

  try {
    const res = await fetch(`/relations/api/person/${EDIT_PERSON_ID}/family`);
    const data = await res.json();

    if (!res.ok) {
      spousesBox.textContent = "تعذّر تحميل بيانات العائلة";
      parentsBox.textContent = "";
      return;
    }

    renderSpousesManage(data.spouses);
    renderParentsManage(data.father, data.mother);
  } catch (e) {
    spousesBox.textContent = "تعذّر الاتصال بالخادم";
    parentsBox.textContent = "";
  }
}

function renderParentsManage(father, mother) {
  const box = document.getElementById("parents-manage-box");
  const parts = [];

  if (father) {
    let text = `الأب: <a href="/persons/${father.id}">${father.full_name}</a>`;
    if (IS_ADMIN) text += ` <button type="button" class="remove-relation-btn" data-relation-id="${father.relation_id}" title="إزالة الأب">✕</button>`;
    parts.push(text);
  }
  if (mother) {
    let text = `الأم: <a href="/persons/${mother.id}">${mother.full_name}</a>`;
    if (mother.tribe) text += ` <span class="muted">(الأخوال: ${mother.tribe})</span>`;
    if (IS_ADMIN) text += ` <button type="button" class="remove-relation-btn" data-relation-id="${mother.relation_id}" title="إزالة الأم">✕</button>`;
    parts.push(text);
  }

  box.innerHTML = parts.length ? parts.join("<br>") : "لا يوجد والدان مسجَّلان بعد.";

  box.querySelectorAll(".remove-relation-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!confirm("هل أنت متأكد من إزالة هذا الرابط؟")) return;
      try {
        const res = await fetch(`/relations/api/${btn.dataset.relationId}/delete`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) { alert(data.error || "تعذّر الحذف"); return; }
        loadFamilyManagement();
      } catch (e) {
        alert("تعذّر الاتصال بالخادم");
      }
    });
  });
}

function renderSpousesManage(spouses) {
  const box = document.getElementById("spouses-manage-box");

  if (!spouses || spouses.length === 0) {
    box.textContent = "لا توجد زوجات/أزواج مسجَّلون بعد.";
    return;
  }

  box.innerHTML = "";

  spouses.forEach(sp => {
    const statusLabel = sp.marriage_status === "current" ? "" :
      ` <span class="muted">(${sp.marriage_status === "divorced" ? "مطلَّقة" : "متوفاة"})</span>`;

    const block = document.createElement("div");
    block.className = "spouse-card";
    block.innerHTML = `
      <div class="spouse-header">
        <a href="/persons/${sp.id}" class="spouse-name">${sp.full_name}</a>${statusLabel}
        ${sp.tribe ? `<span class="muted"> — عشيرتها: ${sp.tribe}</span>` : ""}
      </div>
      <ul class="children-ul child-list" data-spouse-id="${sp.id}"></ul>
      <div class="field-row" style="margin-top:10px; align-items:flex-end;">
        <div class="field">
          <label>إضافة ابن/ابنة</label>
          <input type="text" class="new-child-name" placeholder="الاسم الكامل">
        </div>
        <div class="field field-narrow">
          <label>الجنس</label>
          <select class="new-child-gender">
            <option value="male">ذكر</option>
            <option value="female">أنثى</option>
          </select>
        </div>
        <button type="button" class="btn btn-sm add-child-btn" data-spouse-id="${sp.id}">إضافة</button>
      </div>
    `;

    const childList = block.querySelector(".child-list");
    const childTemplate = document.getElementById("child-item-template");

    if (sp.children.length === 0) {
      const empty = document.createElement("li");
      empty.className = "muted small";
      empty.textContent = "لا يوجد أبناء مسجَّلون من هذه الزوجة";
      childList.appendChild(empty);
    } else {
      sp.children.forEach(c => {
        const node = childTemplate.content.cloneNode(true);
        const link = node.querySelector(".child-link");
        link.href = `/persons/${c.id}`;
        link.textContent = c.full_name;

        const removeBtn = node.querySelector(".remove-child-btn");
        if (IS_ADMIN) {
          removeBtn.addEventListener("click", () => handleRemoveChild(sp.id, c.id));
        } else {
          removeBtn.remove();
        }
        childList.appendChild(node);
      });
    }

    block.querySelector(".add-child-btn").addEventListener("click", () => {
      handleAddChild(sp.id, block);
    });

    box.appendChild(block);
  });
}

async function handleAddChild(spouseId, blockEl) {
  const name = blockEl.querySelector(".new-child-name").value.trim();
  const gender = blockEl.querySelector(".new-child-gender").value;

  if (!name) {
    alert("الرجاء إدخال اسم الابن/الابنة");
    return;
  }

  try {
    const res = await fetch(`/persons/api/${EDIT_PERSON_ID}/spouse/${spouseId}/add-child`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: name, gender }),
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "تعذّر الإضافة");
      return;
    }

    loadFamilyManagement();
  } catch (e) {
    alert("تعذّر الاتصال بالخادم");
  }
}

async function handleRemoveChild(spouseId, childId) {
  if (!confirm("هل أنت متأكد من إزالة هذا الابن من هذين الوالدين؟ لن يُحذف سجله بالكامل، فقط الرابط.")) return;

  try {
    const res = await fetch(`/persons/api/${EDIT_PERSON_ID}/spouse/${spouseId}/child/${childId}/remove`, { method: "POST" });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "تعذّر الحذف");
      return;
    }

    loadFamilyManagement();
  } catch (e) {
    alert("تعذّر الاتصال بالخادم");
  }
}

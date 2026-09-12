document.addEventListener("DOMContentLoaded", async () => {
  const spousesBox = document.getElementById("spouses-box");
  const siblingsBox = document.getElementById("siblings-box");
  const parentsLine = document.getElementById("parents-line");

  try {
    const res = await fetch(`/relations/api/person/${PERSON_ID}/family`);
    const data = await res.json();

    if (!res.ok) {
      spousesBox.textContent = "تعذّر تحميل بيانات العائلة";
      siblingsBox.textContent = "";
      return;
    }

    renderParentsLine(data.father, data.mother);
    renderSpouses(data.spouses);
    renderSiblings(data.siblings);
  } catch (e) {
    spousesBox.textContent = "تعذّر الاتصال بالخادم";
    siblingsBox.textContent = "";
  }
});

function renderParentsLine(father, mother) {
  const el = document.getElementById("parents-line");
  const parts = [];

  if (father) {
    let text = `الأب: <a href="/persons/${father.id}">${father.full_name}</a>`;
    if (IS_ADMIN) text += removeBtn(father.relation_id, "إزالة الأب");
    parts.push(text);
  }
  if (mother) {
    let text = `الأم: <a href="/persons/${mother.id}">${mother.full_name}</a>`;
    if (mother.tribe) text += ` <span class="muted">(الأخوال: ${mother.tribe})</span>`;
    if (IS_ADMIN) text += removeBtn(mother.relation_id, "إزالة الأم");
    parts.push(text);
  }

  el.innerHTML = parts.join(" — ");

  if (IS_ADMIN) {
    el.querySelectorAll(".remove-relation-btn").forEach(btn => {
      btn.addEventListener("click", () => handleRemoveRelation(btn.dataset.relationId));
    });
  }
}

function removeBtn(relationId, label) {
  return ` <button type="button" class="remove-relation-btn" data-relation-id="${relationId}" title="${label}">✕</button>`;
}

async function handleRemoveRelation(relationId) {
  if (!confirm("هل أنت متأكد من إزالة هذا الرابط؟ يمكنك بعدها إضافة الوالد الصحيح من زر \"إضافة الوالدين\".")) return;

  try {
    const res = await fetch(`/relations/api/${relationId}/delete`, { method: "POST" });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "تعذّر الحذف");
      return;
    }
    window.location.reload();
  } catch (e) {
    alert("تعذّر الاتصال بالخادم");
  }
}

function renderSpouses(spouses) {
  const box = document.getElementById("spouses-box");

  if (!spouses || spouses.length === 0) {
    box.textContent = "لا توجد زوجات/أزواج مسجَّلون بعد.";
    return;
  }

  box.innerHTML = spouses.map(sp => {
    const statusLabel = sp.marriage_status === "current" ? "" :
      ` <span class="muted">(${sp.marriage_status === "divorced" ? "مطلَّقة" : "متوفاة"})</span>`;

    const childrenHtml = sp.children.length
      ? `<ul class="children-ul">${sp.children.map(c =>
          `<li><a href="/persons/${c.id}">${c.full_name}</a></li>`
        ).join("")}</ul>`
      : `<div class="muted small">لا يوجد أبناء مسجَّلون من هذه الزوجة</div>`;

    return `
      <div class="spouse-card">
        <div class="spouse-header">
          <a href="/persons/${sp.id}" class="spouse-name">${sp.full_name}</a>${statusLabel}
          ${sp.tribe ? `<span class="muted"> — عشيرتها: ${sp.tribe}</span>` : ""}
        </div>
        ${childrenHtml}
      </div>`;
  }).join("");
}

function renderSiblings(siblings) {
  const box = document.getElementById("siblings-box");

  if (!siblings || siblings.length === 0) {
    box.textContent = "لا يوجد إخوة مسجَّلون.";
    return;
  }

  box.innerHTML = `<ul class="children-ul">${siblings.map(s =>
    `<li><a href="/persons/${s.id}">${s.full_name}</a></li>`
  ).join("")}</ul>`;
}

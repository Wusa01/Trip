document.addEventListener("DOMContentLoaded", () => {
  const createForm = document.getElementById("create-tribe-form");
  const createError = document.getElementById("tribe-form-error");
  const tableBody = document.getElementById("tribes-table-body");

  // -------------------------------------------------------------------
  // إضافة عشيرة جديدة
  // -------------------------------------------------------------------
  createForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    createError.style.display = "none";

    const formData = new FormData(createForm);

    try {
      const res = await fetch("/tribes/api/create", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        createError.textContent = data.error || "تعذّر إضافة العشيرة";
        createError.style.display = "block";
        return;
      }

      window.location.reload();
    } catch (err) {
      createError.textContent = "تعذّر الاتصال بالخادم";
      createError.style.display = "block";
    }
  });

  // -------------------------------------------------------------------
  // تعديل / حذف صف موجود (تفويض الأحداث لأن الأزرار قد تُستبدل)
  // -------------------------------------------------------------------
  tableBody.addEventListener("click", (e) => {
    const editBtn = e.target.closest(".edit-btn");
    const deleteBtn = e.target.closest(".delete-btn");
    const saveBtn = e.target.closest(".save-btn");
    const cancelBtn = e.target.closest(".cancel-btn");

    if (editBtn) return startEdit(editBtn.closest("tr"));
    if (deleteBtn) return handleDelete(deleteBtn.closest("tr"));
    if (saveBtn) return handleSave(saveBtn.closest("tr"));
    if (cancelBtn) return cancelEdit(cancelBtn.closest("tr"));
  });

  function startEdit(row) {
    const nameCell = row.querySelector(".tribe-name-cell");
    const branchCell = row.querySelector(".branch-name-cell");
    const actionsCell = row.querySelector(".tribe-actions-cell");

    // حفظ القيم الأصلية لاستعادتها عند الإلغاء
    row.dataset.originalName = nameCell.textContent.trim();
    row.dataset.originalBranch = branchCell.textContent.trim() === "—" ? "" : branchCell.textContent.trim();
    row.dataset.originalActions = actionsCell.innerHTML;

    nameCell.innerHTML = `<input type="text" class="edit-tribe-name" value="${escapeAttr(row.dataset.originalName)}">`;
    branchCell.innerHTML = `<input type="text" class="edit-branch-name" value="${escapeAttr(row.dataset.originalBranch)}">`;
    actionsCell.innerHTML = `
      <button class="btn btn-sm save-btn">حفظ</button>
      <button class="btn btn-outline btn-sm cancel-btn">إلغاء</button>
    `;
  }

  function cancelEdit(row) {
    const nameCell = row.querySelector(".tribe-name-cell");
    const branchCell = row.querySelector(".branch-name-cell");
    const actionsCell = row.querySelector(".tribe-actions-cell");

    nameCell.textContent = row.dataset.originalName;
    branchCell.textContent = row.dataset.originalBranch || "—";
    actionsCell.innerHTML = row.dataset.originalActions;
  }

  async function handleSave(row) {
    const id = row.dataset.id;
    const nameInput = row.querySelector(".edit-tribe-name");
    const branchInput = row.querySelector(".edit-branch-name");

    const formData = new FormData();
    formData.append("tribe_name", nameInput.value);
    formData.append("branch_name", branchInput.value);

    try {
      const res = await fetch(`/tribes/api/${id}/update`, { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        alert(data.error || "تعذّر حفظ التعديل");
        return;
      }

      window.location.reload();
    } catch (err) {
      alert("تعذّر الاتصال بالخادم");
    }
  }

  async function handleDelete(row) {
    if (!confirm("هل أنت متأكد من حذف هذه العشيرة/الفرع؟")) return;

    const id = row.dataset.id;

    try {
      const res = await fetch(`/tribes/api/${id}/delete`, { method: "POST" });
      const data = await res.json();

      if (!res.ok) {
        alert(data.error || "تعذّر حذف العشيرة");
        return;
      }

      row.remove();
    } catch (err) {
      alert("تعذّر الاتصال بالخادم");
    }
  }

  function escapeAttr(str) {
    return String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  }
});

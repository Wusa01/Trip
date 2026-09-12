document.addEventListener("DOMContentLoaded", () => {
  // -------------------------------------------------------------------
  // إضافة مستخدم جديد
  // -------------------------------------------------------------------
  const createForm = document.getElementById("create-user-form");
  const createError = document.getElementById("user-form-error");

  createForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    createError.style.display = "none";

    const formData = new FormData(createForm);

    try {
      const res = await fetch("/auth/api/users/create", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        createError.textContent = data.error || "تعذّر إنشاء المستخدم";
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
  // تعطيل / إعادة تعيين كلمة مرور مستخدم (تفويض الأحداث)
  // -------------------------------------------------------------------
  const tableBody = document.getElementById("users-table-body");

  tableBody.addEventListener("click", (e) => {
    const deactivateBtn = e.target.closest(".deactivate-btn");
    const resetBtn = e.target.closest(".reset-pw-btn");
    const saveResetBtn = e.target.closest(".save-reset-btn");
    const cancelResetBtn = e.target.closest(".cancel-reset-btn");

    if (deactivateBtn) return handleDeactivate(deactivateBtn.closest("tr"));
    if (resetBtn) return startResetPassword(resetBtn.closest("tr"));
    if (saveResetBtn) return handleSaveReset(saveResetBtn.closest("tr"));
    if (cancelResetBtn) return cancelResetPassword(cancelResetBtn.closest("tr"));
  });

  async function handleDeactivate(row) {
    if (!confirm("هل أنت متأكد من تعطيل هذا المستخدم؟")) return;
    const id = row.dataset.id;

    try {
      const res = await fetch(`/auth/api/users/${id}/deactivate`, { method: "POST" });
      const data = await res.json();

      if (!res.ok) {
        alert(data.error || "تعذّر تعطيل المستخدم");
        return;
      }
      row.remove();
    } catch (err) {
      alert("تعذّر الاتصال بالخادم");
    }
  }

  function startResetPassword(row) {
    const actionsCell = row.querySelector(".user-actions-cell");
    row.dataset.originalActions = actionsCell.innerHTML;

    actionsCell.innerHTML = `
      <input type="password" class="reset-pw-new" placeholder="كلمة مرور جديدة" style="width:130px;">
      <input type="password" class="reset-pw-confirm" placeholder="تأكيد" style="width:110px;">
      <button class="btn btn-sm save-reset-btn">حفظ</button>
      <button class="btn btn-outline btn-sm cancel-reset-btn">إلغاء</button>
    `;
  }

  function cancelResetPassword(row) {
    const actionsCell = row.querySelector(".user-actions-cell");
    actionsCell.innerHTML = row.dataset.originalActions;
  }

  async function handleSaveReset(row) {
    const id = row.dataset.id;
    const newPw = row.querySelector(".reset-pw-new").value;
    const confirmPw = row.querySelector(".reset-pw-confirm").value;

    const formData = new FormData();
    formData.append("new_password", newPw);
    formData.append("confirm_password", confirmPw);

    try {
      const res = await fetch(`/auth/api/users/${id}/reset-password`, { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        alert(data.error || "تعذّر إعادة تعيين كلمة المرور");
        return;
      }

      alert("تم تغيير كلمة المرور بنجاح.");
      cancelResetPassword(row);
    } catch (err) {
      alert("تعذّر الاتصال بالخادم");
    }
  }

  // -------------------------------------------------------------------
  // إرسال نسخة احتياطية بالبريد
  // -------------------------------------------------------------------
  const emailBackupForm = document.getElementById("email-backup-form");
  const emailBackupError = document.getElementById("email-backup-error");
  const emailBackupSuccess = document.getElementById("email-backup-success");

  emailBackupForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    emailBackupError.style.display = "none";
    emailBackupSuccess.style.display = "none";

    const submitBtn = emailBackupForm.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    submitBtn.textContent = "جارٍ الإرسال...";

    const formData = new FormData(emailBackupForm);

    try {
      const res = await fetch("/auth/backup/email", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        emailBackupError.textContent = data.error || "تعذّر إرسال النسخة الاحتياطية";
        emailBackupError.style.display = "block";
        return;
      }

      emailBackupSuccess.style.display = "block";
    } catch (err) {
      emailBackupError.textContent = "تعذّر الاتصال بالخادم";
      emailBackupError.style.display = "block";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "إرسال نسخة بالبريد الآن";
    }
  });

  // -------------------------------------------------------------------
  // استيراد نسخة بيانات
  // -------------------------------------------------------------------
  const importForm = document.getElementById("import-form");
  const importError = document.getElementById("import-error");

  importForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    importError.style.display = "none";

    if (!confirm("سيتم استبدال كل البيانات الحالية بمحتوى الملف المرفوع. هل أنت متأكد؟")) {
      return;
    }

    const submitBtn = importForm.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    submitBtn.textContent = "جارٍ الاستيراد...";

    const formData = new FormData(importForm);

    try {
      const res = await fetch("/auth/backup/import", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        importError.textContent = data.error || "تعذّر استيراد الملف";
        importError.style.display = "block";
        return;
      }

      alert(data.message || "تم استيراد البيانات بنجاح.");
      window.location.href = data.redirect || "/auth/login";
    } catch (err) {
      importError.textContent = "تعذّر الاتصال بالخادم";
      importError.style.display = "block";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "استيراد الآن";
    }
  });
});

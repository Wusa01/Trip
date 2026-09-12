document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".approve-btn").forEach(btn => {
    btn.addEventListener("click", () => handleDecision(btn.dataset.id, "approve"));
  });

  document.querySelectorAll(".reject-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const reason = prompt("سبب الرفض (اختياري):", "");
      handleDecision(btn.dataset.id, "reject", reason || "");
    });
  });
});

async function handleDecision(relationId, action, reason = "") {
  const formData = new FormData();
  if (reason) formData.append("reason", reason);

  try {
    const res = await fetch(`/relations/api/${relationId}/${action}`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "حدث خطأ أثناء تنفيذ الإجراء");
      return;
    }

    // إزالة الصف من الجدول فور نجاح الاعتماد أو الرفض
    const row = document.getElementById(`row-${relationId}`);
    if (row) row.remove();
  } catch (e) {
    alert("تعذّر الاتصال بالخادم");
  }
}

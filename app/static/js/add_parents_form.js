document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("add-parents-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.getElementById("form-error");
    errorBox.hidden = true;

    const fatherName = document.getElementById("father_name").value.trim();
    const motherName = document.getElementById("mother_name").value.trim();

    const payload = {
      father: fatherName ? {
        full_name: fatherName,
        tribe_name: document.getElementById("father_tribe").value.trim() || null,
      } : null,
      mother: motherName ? {
        full_name: motherName,
        tribe_name: document.getElementById("mother_tribe").value.trim() || null,
      } : null,
    };

    try {
      const res = await fetch(`/persons/api/${CHILD_PERSON_ID}/add-parents`, {
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

      window.location.href = `/persons/${CHILD_PERSON_ID}`;
    } catch (err) {
      errorBox.textContent = "تعذّر الاتصال بالخادم";
      errorBox.hidden = false;
    }
  });
});

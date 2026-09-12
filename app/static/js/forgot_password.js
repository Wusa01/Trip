document.addEventListener("DOMContentLoaded", () => {
  const step1Form = document.getElementById("forgot-step1");
  const step1Error = document.getElementById("forgot-step1-error");
  const step1Submit = document.getElementById("forgot-step1-submit");

  const step2Form = document.getElementById("forgot-step2");
  const step2Error = document.getElementById("forgot-step2-error");
  const step2EmailLabel = document.getElementById("forgot-step2-email");
  const backBtn = document.getElementById("forgot-back-btn");

  // -------------------------------------------------------------------
  // الخطوة 1: طلب رمز التفعيل بالبريد
  // -------------------------------------------------------------------
  step1Form.addEventListener("submit", async (e) => {
    e.preventDefault();
    step1Error.style.display = "none";

    step1Submit.disabled = true;
    step1Submit.textContent = "جارٍ إرسال الرمز...";

    const formData = new FormData(step1Form);

    try {
      const res = await fetch("/auth/forgot-password/request-code", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        step1Error.textContent = data.error || "تعذّر إرسال رمز التفعيل";
        step1Error.style.display = "block";
        return;
      }

      step2EmailLabel.textContent = data.email;
      step1Form.hidden = true;
      step2Form.hidden = false;
      document.getElementById("forgot_code").focus();
    } catch (err) {
      step1Error.textContent = "تعذّر الاتصال بالخادم";
      step1Error.style.display = "block";
    } finally {
      step1Submit.disabled = false;
      step1Submit.textContent = "إرسال رمز التفعيل";
    }
  });

  // -------------------------------------------------------------------
  // الخطوة 2: تأكيد الرمز وتعيين كلمة مرور جديدة
  // -------------------------------------------------------------------
  step2Form.addEventListener("submit", async (e) => {
    e.preventDefault();
    step2Error.style.display = "none";

    const newPassword = document.getElementById("forgot_new_password").value;
    const confirmPassword = document.getElementById("forgot_confirm_password").value;
    if (newPassword !== confirmPassword) {
      step2Error.textContent = "كلمتا المرور غير متطابقتين";
      step2Error.style.display = "block";
      return;
    }

    const formData = new FormData(step2Form);

    try {
      const res = await fetch("/auth/forgot-password/confirm", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        step2Error.textContent = data.error || "تعذّر تغيير كلمة المرور";
        step2Error.style.display = "block";
        return;
      }

      window.location.href = data.redirect || "/";
    } catch (err) {
      step2Error.textContent = "تعذّر الاتصال بالخادم";
      step2Error.style.display = "block";
    }
  });

  // -------------------------------------------------------------------
  // رجوع لخطوة البريد
  // -------------------------------------------------------------------
  backBtn.addEventListener("click", () => {
    step2Form.hidden = true;
    step1Form.hidden = false;
  });
});

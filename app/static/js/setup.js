document.addEventListener("DOMContentLoaded", () => {
  const step1Form = document.getElementById("setup-step1");
  const step1Error = document.getElementById("setup-step1-error");
  const step1Submit = document.getElementById("setup-step1-submit");

  const step2Form = document.getElementById("setup-step2");
  const step2Error = document.getElementById("setup-step2-error");
  const step2EmailLabel = document.getElementById("setup-step2-email");
  const backBtn = document.getElementById("setup-back-btn");

  // -------------------------------------------------------------------
  // الخطوة 1: إرسال البيانات وطلب رمز التفعيل
  // -------------------------------------------------------------------
  step1Form.addEventListener("submit", async (e) => {
    e.preventDefault();
    step1Error.style.display = "none";

    const password = document.getElementById("setup_password").value;
    const confirm = document.getElementById("setup_confirm_password").value;
    if (password !== confirm) {
      step1Error.textContent = "كلمتا المرور غير متطابقتين";
      step1Error.style.display = "block";
      return;
    }

    step1Submit.disabled = true;
    step1Submit.textContent = "جارٍ إرسال الرمز...";

    const formData = new FormData(step1Form);

    try {
      const res = await fetch("/auth/setup/request-code", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        step1Error.textContent = data.error || "تعذّر إرسال رمز التفعيل";
        step1Error.style.display = "block";
        return;
      }

      step2EmailLabel.textContent = data.email;
      step1Form.hidden = true;
      step2Form.hidden = false;
      document.getElementById("setup_code").focus();
    } catch (err) {
      step1Error.textContent = "تعذّر الاتصال بالخادم";
      step1Error.style.display = "block";
    } finally {
      step1Submit.disabled = false;
      step1Submit.textContent = "إرسال رمز التفعيل إلى بريدي";
    }
  });

  // -------------------------------------------------------------------
  // الخطوة 2: تأكيد الرمز وإنشاء الحساب
  // -------------------------------------------------------------------
  step2Form.addEventListener("submit", async (e) => {
    e.preventDefault();
    step2Error.style.display = "none";

    const formData = new FormData(step2Form);

    try {
      const res = await fetch("/auth/setup/confirm", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        step2Error.textContent = data.error || "رمز التفعيل غير صحيح";
        step2Error.style.display = "block";
        return;
      }

      window.location.href = data.redirect || "/dashboard";
    } catch (err) {
      step2Error.textContent = "تعذّر الاتصال بالخادم";
      step2Error.style.display = "block";
    }
  });

  // -------------------------------------------------------------------
  // رجوع لتعديل البيانات (بدون إعادة تحميل الصفحة)
  // -------------------------------------------------------------------
  backBtn.addEventListener("click", () => {
    step2Form.hidden = true;
    step1Form.hidden = false;
  });
});

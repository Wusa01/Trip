document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("profile-form");
  const errorBox = document.getElementById("profile-error");
  const successBox = document.getElementById("profile-success");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.style.display = "none";
    successBox.style.display = "none";

    const newPassword = document.getElementById("profile_new_password").value;
    const confirmNewPassword = document.getElementById("profile_confirm_new_password").value;
    if (newPassword && newPassword !== confirmNewPassword) {
      errorBox.textContent = "كلمتا المرور الجديدة غير متطابقتين";
      errorBox.style.display = "block";
      return;
    }

    const formData = new FormData(form);

    try {
      const res = await fetch("/auth/profile/update", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        errorBox.textContent = data.error || "تعذّر حفظ التعديلات";
        errorBox.style.display = "block";
        return;
      }

      // تفريغ حقول كلمة المرور بعد الحفظ الناجح، وإبقاء الاسم/البريد كما أُدخلا
      document.getElementById("profile_new_password").value = "";
      document.getElementById("profile_confirm_new_password").value = "";
      document.getElementById("profile_current_password").value = "";
      successBox.style.display = "block";
    } catch (err) {
      errorBox.textContent = "تعذّر الاتصال بالخادم";
      errorBox.style.display = "block";
    }
  });
});

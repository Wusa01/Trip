let selectedA = null;
let selectedB = null;
let relCy = null;

document.addEventListener("DOMContentLoaded", () => {
  setupPersonPicker("person-a-input", "person-a-results", "person-a-id", "person-a-confirm", (p) => selectedA = p);
  setupPersonPicker("person-b-input", "person-b-results", "person-b-id", "person-b-confirm", (p) => selectedB = p);

  document.getElementById("find-btn").addEventListener("click", handleFind);
});

function setupPersonPicker(inputId, resultsId, hiddenId, confirmId, onSelect) {
  const input = document.getElementById(inputId);
  const resultsBox = document.getElementById(resultsId);
  const hiddenInput = document.getElementById(hiddenId);
  const confirmBox = document.getElementById(confirmId);
  let debounceTimer = null;
  let currentResults = [];

  function closeDropdown() {
    resultsBox.hidden = true;
    resultsBox.innerHTML = "";
  }

  function selectItem(item) {
    input.value = item.full_name;
    hiddenInput.value = item.id;
    closeDropdown();
    confirmBox.textContent = `✓ تم اختيار: ${item.full_name} (${item.public_id})`;
    confirmBox.hidden = false;
    onSelect({ id: item.id, name: item.full_name });
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    hiddenInput.value = "";
    confirmBox.hidden = true;
    const query = input.value.trim();

    if (query.length < 2) {
      closeDropdown();
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/relationship/api/search?q=${encodeURIComponent(query)}`);
        const results = await res.json();
        currentResults = results;
        renderDropdown(results);
      } catch (e) {
        closeDropdown();
      }
    }, 250);
  });

  function renderDropdown(results) {
    if (!results.length) {
      resultsBox.innerHTML = `<div class="picker-empty muted small">لا توجد نتائج مطابقة</div>`;
      resultsBox.hidden = false;
      return;
    }

    // نفس بنية نتائج صفحة البحث (result-row / result-name / result-main)
    resultsBox.innerHTML = `<div class="results-list">` +
      results.map((r, idx) => `
        <div class="result-row picker-result-row" data-idx="${idx}">
          <div class="result-main">
            <div class="result-name">${r.full_name}</div>
            <div class="muted small">${r.public_id}</div>
          </div>
        </div>
      `).join("") +
    `</div>`;
    resultsBox.hidden = false;

    resultsBox.querySelectorAll(".picker-result-row").forEach(row => {
      row.addEventListener("click", () => selectItem(currentResults[parseInt(row.dataset.idx, 10)]));
    });
  }

  // الضغط على Enter يختار أول نتيجة ظاهرة تلقائياً
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!resultsBox.hidden && currentResults.length > 0) {
        selectItem(currentResults[0]);
      }
    }
  });

  document.addEventListener("click", (e) => {
    if (!resultsBox.contains(e.target) && e.target !== input) {
      closeDropdown();
    }
  });
}

async function handleFind() {
  const errorBox = document.getElementById("finder-error");
  errorBox.hidden = true;

  const aId = document.getElementById("person-a-id").value;
  const bId = document.getElementById("person-b-id").value;

  if (!aId || !bId) {
    errorBox.textContent = "الرجاء اختيار الاسم من القائمة المنسدلة (أو اضغط Enter بعد الكتابة).";
    errorBox.hidden = false;
    return;
  }

  try {
    const res = await fetch(`/relationship/api/find?a=${aId}&b=${bId}`);
    const data = await res.json();

    if (!res.ok) {
      errorBox.textContent = data.error || "تعذّر إيجاد العلاقة";
      errorBox.hidden = false;
      document.getElementById("result-card").hidden = true;
      return;
    }

    renderResult(data);
  } catch (e) {
    errorBox.textContent = "تعذّر الاتصال بالخادم";
    errorBox.hidden = false;
  }
}

function renderResult(data) {
  document.getElementById("result-card").hidden = false;

  const summary = document.getElementById("relation-summary");
  summary.innerHTML = `
    <div class="relation-headline">
      <strong>${data.person_a.full_name}</strong> و<strong>${data.person_b.full_name}</strong>
    </div>
    <div class="relation-type-badge">${data.relation_label}</div>
    <div class="muted small">
      يلتقيان عند السلف المشترك: <a href="/persons/${data.common_ancestor.id}">${data.common_ancestor.full_name}</a>
      — ${data.person_a.full_name} يبعد عنه ${data.depth_a} ${data.depth_a === 1 ? "جيل" : "أجيال"}،
      ${data.person_b.full_name} يبعد عنه ${data.depth_b} ${data.depth_b === 1 ? "جيل" : "أجيال"}
    </div>
  `;

  renderPathDiagram(data);
  renderPathList(data);
}

function renderPathDiagram(data) {
  const container = document.getElementById("rel-cy");

  if (relCy) relCy.destroy();

  const nodes = data.path.map(p => ({
    data: {
      id: `p${p.id}`,
      label: p.full_name,
      gender: p.gender,
      isEndpoint: (p.id === data.person_a.id || p.id === data.person_b.id) ? true : undefined,
      isAncestor: (p.id === data.common_ancestor.id) ? true : undefined,
    },
  }));

  const edges = [];
  for (let i = 0; i < data.path.length - 1; i++) {
    edges.push({
      data: { id: `e${i}`, source: `p${data.path[i].id}`, target: `p${data.path[i + 1].id}` },
    });
  }

  relCy = cytoscape({
    container,
    elements: [...nodes, ...edges],
    style: [
      {
        selector: "node",
        style: {
          "background-color": "#fff",
          "border-width": 2,
          "border-color": "#0f4c4c",
          "label": "data(label)",
          "text-valign": "center",
          "text-halign": "center",
          "font-family": "Cairo, sans-serif",
          "font-size": "12px",
          "width": "label",
          "height": 36,
          "padding": "12px",
          "shape": "round-rectangle",
        },
      },
      { selector: "node[gender = 'female']", style: { "border-color": "#b06a8f" } },
      { selector: "node[isAncestor]", style: { "background-color": "#d4a24c", "border-color": "#d4a24c", "color": "#fff", "font-weight": "bold" } },
      { selector: "node[isEndpoint]", style: { "border-width": 3 } },
      { selector: "edge", style: { "width": 2, "line-color": "#94a3b8", "curve-style": "bezier", "target-arrow-shape": "none" } },
    ],
    layout: { name: "breadthfirst", directed: false, spacingFactor: 1.3 },
  });

  relCy.on("tap", "node", (evt) => {
    const idAttr = evt.target.data("id");
    window.location.href = `/persons/${idAttr.slice(1)}`;
  });
}

function renderPathList(data) {
  const box = document.getElementById("path-list");
  box.innerHTML = `<h3 style="font-size:0.95rem; margin-bottom:8px;">المسار الكامل</h3>` +
    `<div class="path-chain">` +
    data.path.map((p, idx) => {
      const isAncestor = p.id === data.common_ancestor.id;
      return `<a href="/persons/${p.id}" class="path-node ${isAncestor ? 'path-node-ancestor' : ''}">${p.full_name}</a>` +
             (idx < data.path.length - 1 ? `<span class="path-arrow">←</span>` : "");
    }).join("") +
    `</div>`;
}

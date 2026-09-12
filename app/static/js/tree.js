let currentUp = 2;
let currentDown = 2;
let cy = null;

const INK = "#1e2a24";
const GOLD = "#d4a24c";
const PRIMARY = "#0f4c4c";
const MALE_COLOR = "#0f4c4c";
const FEMALE_COLOR = "#b06a8f";
const PAPER = "#ffffff";
const LINE_PARENT = "#94a3b8";
const LINE_MARRIAGE = "#d4a24c";

document.addEventListener("DOMContentLoaded", () => {
  initTree();
  setupToolbar();
  setupSearch();
});

function initTree() {
  cy = cytoscape({
    container: document.getElementById("cy"),
    style: [
      {
        selector: "node",
        style: {
          "background-color": PAPER,
          "border-width": 2,
          "border-color": MALE_COLOR,
          "label": "data(label)",
          "text-valign": "center",
          "text-halign": "center",
          "font-family": "Cairo, sans-serif",
          "font-size": "12px",
          "color": INK,
          "width": "label",
          "height": 36,
          "padding": "12px",
          "shape": "round-rectangle",
        },
      },
      {
        selector: "node[gender = 'female']",
        style: { "border-color": FEMALE_COLOR },
      },
      {
        selector: "node[isCenter]",
        style: {
          "background-color": GOLD,
          "border-color": GOLD,
          "color": "#fff",
          "font-weight": "bold",
        },
      },
      {
        selector: "node[status != 'approved']",
        style: { "border-style": "dashed" },
      },
      {
        selector: "edge[type = 'parent']",
        style: {
          "width": 1.6,
          "line-color": LINE_PARENT,
          "target-arrow-color": LINE_PARENT,
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
        },
      },
      {
        selector: "edge[type = 'marriage']",
        style: {
          "width": 1.6,
          "line-color": LINE_MARRIAGE,
          "line-style": "dashed",
          "curve-style": "bezier",
          "target-arrow-shape": "none",
        },
      },
    ],
    layout: { name: "breadthfirst", directed: true, spacingFactor: 1.25 },
  });

  cy.on("tap", "node", (evt) => {
    const id = evt.target.data("personId");
    if (id) window.location.href = `/persons/${id}`;
  });

  loadSubtree();
}

function setupToolbar() {
  document.getElementById("expand-up").addEventListener("click", () => {
    currentUp += 1;
    loadSubtree();
  });
  document.getElementById("expand-down").addEventListener("click", () => {
    currentDown += 1;
    loadSubtree();
  });
  document.getElementById("fit-view").addEventListener("click", () => {
    cy.fit(undefined, 40);
  });
  document.getElementById("recenter-view").addEventListener("click", () => {
    const centerNode = cy.getElementById(`p${PERSON_ID}`);
    if (centerNode.length) {
      cy.animate({ center: { eles: centerNode }, zoom: 1 }, { duration: 300 });
    }
  });
}

async function loadSubtree() {
  const statusEl = document.getElementById("tree-status");
  statusEl.textContent = "جارٍ التحميل...";

  try {
    const res = await fetch(`/tree/api/${PERSON_ID}/subtree?up=${currentUp}&down=${currentDown}`);
    const data = await res.json();

    if (!res.ok) {
      statusEl.textContent = data.error || "تعذّر تحميل الشجرة";
      return;
    }

    const elements = [
      ...data.nodes.map(n => ({
        data: {
          id: `p${n.id}`,
          personId: n.id,
          label: n.full_name,
          gender: n.gender,
          status: n.status,
          isCenter: n.is_center ? true : undefined,
        },
      })),
      ...data.edges.map(e => ({
        data: {
          id: `${e.type}-${e.source}-${e.target}`,
          source: `p${e.source}`,
          target: `p${e.target}`,
          type: e.type,
        },
      })),
    ];

    cy.elements().remove();
    cy.add(elements);
    cy.layout({ name: "breadthfirst", directed: true, spacingFactor: 1.25 }).run();

    const marriageCount = data.edges.filter(e => e.type === "marriage").length;
    statusEl.textContent = `${data.nodes.length} فرد — ${marriageCount} رابط زواج`;
  } catch (e) {
    statusEl.textContent = "تعذّر الاتصال بالخادم";
  }
}

// ---------------------------------------------------------------------------
// بحث سريع للتنقل بين الأشخاص داخل شاشة الشجرة
// ---------------------------------------------------------------------------

function setupSearch() {
  const input = document.getElementById("tree-search-input");
  const resultsBox = document.getElementById("tree-search-results");
  let debounceTimer = null;

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const query = input.value.trim();

    if (query.length < 2) {
      resultsBox.hidden = true;
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/tree/api/search?q=${encodeURIComponent(query)}`);
        const results = await res.json();
        renderSearchResults(results, resultsBox);
      } catch (e) {
        resultsBox.hidden = true;
      }
    }, 250);
  });

  document.addEventListener("click", (e) => {
    if (!resultsBox.contains(e.target) && e.target !== input) {
      resultsBox.hidden = true;
    }
  });
}

function renderSearchResults(results, resultsBox) {
  if (!results.length) {
    resultsBox.innerHTML = `<div class="tree-search-empty">لا توجد نتائج</div>`;
    resultsBox.hidden = false;
    return;
  }

  resultsBox.innerHTML = results.map(r =>
    `<a href="/tree/${r.id}" class="tree-search-item">${r.full_name} <span class="muted small">${r.public_id}</span></a>`
  ).join("");
  resultsBox.hidden = false;
}

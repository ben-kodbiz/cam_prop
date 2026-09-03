/* Home page: latest approved claims, companies, alternatives. */

function renderCompaniesInto(container, companies, limit) {
  container.innerHTML = "";
  if (!companies.length) {
    empty(container, "No corporate records published yet.");
    return;
  }
  companies.slice(0, limit || companies.length).forEach(c => {
    const el = document.createElement("article");
    el.className = "card";
    const h = document.createElement("h3");
    h.textContent = c.company;
    el.appendChild(h);
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = c.service + " · " + c.customer + " · " + c.classification.replace(/_/g, " ");
    el.appendChild(meta);
    container.appendChild(el);
  });
}

function renderAlternativesInto(container, alternatives, limit) {
  container.innerHTML = "";
  if (!alternatives.length) {
    empty(container, "No alternatives published yet.");
    return;
  }
  alternatives.slice(0, limit || alternatives.length).forEach(a => {
    const el = document.createElement("article");
    el.className = "card";
    const h = document.createElement("h3");
    h.textContent = a.alternative + " (replaces " + a.product + ")";
    el.appendChild(h);
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent =
      a.category.replace(/_/g, " ") +
      (a.alternative_license ? " · " + a.alternative_license : "") +
      (a.migration_difficulty ? " · migration: " + a.migration_difficulty : "");
    el.appendChild(meta);
    container.appendChild(el);
  });
}

async function loadHome() {
  const claimsEl = document.getElementById("claims-list");
  const companiesEl = document.getElementById("companies-list");
  const alternativesEl = document.getElementById("alternatives-list");
  try {
    const claims = await DATA.claims();
    renderClaimsInto(claimsEl, claims, 10);
    renderCompaniesInto(companiesEl, await DATA.companies(), 5);
    renderAlternativesInto(alternativesEl, await DATA.alternatives(), 5);
  } catch (e) {
    empty(claimsEl, "Failed to load data.");
    console.error(e);
  }
}

loadHome();

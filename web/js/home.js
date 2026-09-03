/* Home page: latest approved claims, legal records, companies, alternatives. */

function renderLegalInto(container, legal, limit) {
    container.innerHTML = "";
    if (!legal.length) {
        const p = document.createElement("p");
        p.className = "loading";
        p.textContent = "No legal records published yet.";
        container.appendChild(p);
        return;
    }
    const TYPES = {
        allegation: "Allegation",
        provisional_measure: "Provisional measure",
        advisory_opinion: "Advisory opinion",
        judgment: "Judgment",
        arrest_warrant: "Arrest warrant",
        conviction: "Conviction",
        investigative_finding: "Investigative finding",
        political_resolution: "Political resolution",
    };
    legal.slice(0, limit || legal.length).forEach(ld => {
        const el = document.createElement("article");
        el.className = "card";
        const h = document.createElement("h3");
        h.textContent = ld.body + " — " + ld.case_or_document;
        el.appendChild(h);
        const pill = document.createElement("span");
        pill.className = "status-pill " + ld.document_type;
        pill.textContent = TYPES[ld.document_type] || ld.document_type;
        el.appendChild(pill);
        const meta = document.createElement("p");
        meta.className = "meta";
        meta.textContent = (ld.date || "undated") + " — " + ld.finding;
        el.appendChild(meta);
        container.appendChild(el);
    });
}

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
    const legalEl = document.getElementById("legal-preview");
    const companiesEl = document.getElementById("companies-list");
    const alternativesEl = document.getElementById("alternatives-list");
    try {
        const claims = await DATA.claims();
        renderClaimsInto(claimsEl, claims, 10);
        renderLegalInto(legalEl, await fetch("/data/legal.json").then(r => r.ok ? r.json() : []), 3);
        renderCompaniesInto(companiesEl, await DATA.companies(), 5);
        renderAlternativesInto(alternativesEl, await DATA.alternatives(), 5);
    } catch (e) {
        empty(claimsEl, "Failed to load data.");
        console.error(e);
    }
}

loadHome();

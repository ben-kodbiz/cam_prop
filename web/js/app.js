/* Shared helpers for Open Evidence static frontend. */

const DATA = {
  claims: () => fetch("/data/claims.json").then(r => r.ok ? r.json() : []),
  sources: () => fetch("/data/sources.json").then(r => r.ok ? r.json() : []),
  companies: () => fetch("/data/companies.json").then(r => r.ok ? r.json() : []),
  alternatives: () => fetch("/data/alternatives.json").then(r => r.ok ? r.json() : []),
};

function statusPill(status) {
  const span = document.createElement("span");
  span.className = "status-pill " + status;
  span.textContent = status.replace(/_/g, " ");
  return span;
}

function claimCard(claim) {
  const el = document.createElement("article");
  el.className = "card claim-card";
  const h = document.createElement("h2");
  const a = document.createElement("a");
  a.href = "/claim.html?id=" + encodeURIComponent(claim.id);
  a.textContent = claim.claim_text;
  h.appendChild(a);
  el.appendChild(h);
  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent =
    (claim.speaker || "Unknown speaker") +
    (claim.published_at ? " · " + claim.published_at : "") +
    " · " + claim.id;
  el.appendChild(meta);
  const pill = statusPill(claim.status);
  el.appendChild(pill);
  const conf = document.createElement("span");
  conf.className = "confidence";
  conf.textContent = " " + Math.round((claim.confidence || 0) * 100) + "% confidence";
  el.appendChild(conf);
  return el;
}

function empty(container, message) {
  container.innerHTML = "";
  const p = document.createElement("p");
  p.className = "loading";
  p.textContent = message;
  container.appendChild(p);
}

function params() {
  return new URLSearchParams(window.location.search);
}

function renderClaimsInto(container, claims, limit) {
  container.innerHTML = "";
  if (!claims.length) {
    empty(container, "No claims published yet.");
    return;
  }
  claims.slice(0, limit || claims.length).forEach(c => container.appendChild(claimCard(c)));
}

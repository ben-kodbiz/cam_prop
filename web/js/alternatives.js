/* Alternatives page. */

async function loadAlternatives() {
  const container = document.getElementById("alternatives-list");
  const alternatives = await DATA.alternatives();
  container.innerHTML = "";
  if (!alternatives.length) {
    empty(container, "No alternatives published yet.");
    return;
  }
  const byCategory = {};
  alternatives.forEach(a => {
    (byCategory[a.category] = byCategory[a.category] || []).push(a);
  });
  Object.keys(byCategory).sort().forEach(cat => {
    const h = document.createElement("h2");
    h.textContent = cat.replace(/_/g, " ");
    container.appendChild(h);
    byCategory[cat].forEach(a => {
      const el = document.createElement("article");
      el.className = "card";
      const h3 = document.createElement("h3");
      let name = a.alternative;
      if (a.alternative_url) {
        const link = document.createElement("a");
        link.href = a.alternative_url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = name;
        h3.appendChild(link);
      } else {
        h3.textContent = name;
      }
      el.appendChild(h3);
      const meta = document.createElement("p");
      meta.className = "meta";
      meta.textContent = "Replaces: " + a.product + (a.company ? " (" + a.company + ")" : "");
      el.appendChild(meta);
      const details = document.createElement("p");
      details.textContent =
        (a.alternative_license ? "License: " + a.alternative_license + ". " : "") +
        (a.self_hosting_available ? "Self-hosting available. " : "") +
        (a.migration_difficulty ? "Migration: " + a.migration_difficulty + ". " : "");
      el.appendChild(details);
      if (a.privacy_notes) {
        const p = document.createElement("p");
        p.className = "meta";
        p.textContent = a.privacy_notes;
        el.appendChild(p);
      }
      container.appendChild(el);
    });
  });
}

loadAlternatives();

/* Sources page with tier labels. */

function tierName(tier) {
  return { 1: "Tier 1 — Primary", 2: "Tier 2 — Professional journalism",
           3: "Tier 3 — Specialist investigation", 4: "Tier 4 — Social media" }[tier] ||
         "Tier " + tier;
}

async function loadSources() {
  const container = document.getElementById("sources-list");
  const sources = await DATA.sources();
  container.innerHTML = "";
  if (!sources.length) {
    empty(container, "No sources published yet.");
    return;
  }
  sources.forEach(s => {
    const el = document.createElement("article");
    el.className = "card";
    const h = document.createElement("h3");
    if (s.doc_kind === "book") {
      h.textContent = s.title + (s.book_year ? " (" + s.book_year + ")" : "");
    } else {
      const a = document.createElement("a");
      a.href = s.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = s.title;
      h.appendChild(a);
    }
    el.appendChild(h);
    const meta = document.createElement("p");
    meta.className = "meta";
    if (s.doc_kind === "book") {
      const author = s.book_author || "Unknown author";
      const pages = s.book_pages ? " · " + s.book_pages + " pp." : "";
      const isbn = s.book_isbn ? " · ISBN " + s.book_isbn : "";
      meta.textContent = author + pages + isbn + " · " + tierName(s.source_tier) + " · " + s.id;
    } else {
      meta.textContent = (s.publisher || "Unknown publisher") +
        " · " + tierName(s.source_tier) +
        (s.published_at ? " · " + s.published_at : "") +
        " · " + s.id;
    }
    el.appendChild(meta);
    container.appendChild(el);
  });
}

loadSources();

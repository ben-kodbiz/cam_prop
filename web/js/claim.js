/* Single claim page with full evidence display. */

function evidenceSection(title, items, sources) {
  const block = document.createElement("div");
  block.className = "evidence-block";
  const h = document.createElement("h3");
  h.textContent = title;
  block.appendChild(h);
  if (!items.length) {
    const p = document.createElement("p");
    p.textContent = "None recorded.";
    block.appendChild(p);
    return block;
  }
  items.forEach(ev => {
    const item = document.createElement("div");
    item.className = "evidence-item";
    const src = document.createElement("div");
    const link = document.createElement("a");
    link.href = ev.url;
    link.target = "_blank";
    link.rel = "noopener";
    let label = (ev.publisher || "Source") + (ev.published_at ? " · " + ev.published_at : "");
    if (ev.page_number) {
      label += " · p." + ev.page_number;
    } else if (ev.section) {
      label += " · " + ev.section;
    }
    link.textContent = label;
    src.appendChild(link);
    src.className = "source";
    item.appendChild(src);
    if (ev.excerpt) {
      const ex = document.createElement("p");
      ex.textContent = "\u201c" + ev.excerpt + "\u201d";
      item.appendChild(ex);
    }
    block.appendChild(item);
  });
  return block;
}

async function loadClaim() {
  const main = document.getElementById("claim-page");
  const id = params().get("id");
  const claims = await DATA.claims();
  const claim = claims.find(c => c.id === id);
  main.innerHTML = "";
  if (!claim) {
    const p = document.createElement("p");
    p.textContent = "Claim not found. It may not be published yet — only approved claims appear on this site.";
    main.appendChild(p);
    return;
  }
  const h = document.createElement("h1");
  h.textContent = "Claim";
  main.appendChild(h);

  const card = document.createElement("article");
  card.className = "card claim-card";
  const claimText = document.createElement("p");
  claimText.className = "claim-text";
  claimText.textContent = "\u201c" + claim.claim_text + "\u201d";
  card.appendChild(claimText);

  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent =
    "Who: " + (claim.speaker || "Unknown") +
    (claim.published_at ? " · When: " + claim.published_at : "") +
    " · ID: " + claim.id;
  card.appendChild(meta);

  const assess = document.createElement("h2");
  assess.textContent = "Assessment";
  card.appendChild(assess);
  card.appendChild(statusPill(claim.status));
  const conf = document.createElement("span");
  conf.className = "confidence";
  conf.textContent = " " + Math.round((claim.confidence || 0) * 100) + "% confidence";
  card.appendChild(conf);

  card.appendChild(evidenceSection("Supporting evidence",
    claim.evidence.filter(e => e.relationship === "supports")));
  card.appendChild(evidenceSection("Contradicting evidence",
    claim.evidence.filter(e => e.relationship === "contradicts")));
  card.appendChild(evidenceSection("Context",
    claim.evidence.filter(e => e.relationship === "context")));

  const dont = document.createElement("div");
  dont.className = "evidence-block";
  const dh = document.createElement("h3");
  dh.textContent = "What we don\u2019t know";
  dont.appendChild(dh);
  const dp = document.createElement("p");
  dp.textContent = (claim.status === "unknown" || claim.status === "insufficient_evidence" || claim.status === "disputed")
    ? "Evidence is incomplete or contested; see the methodology page for how this is handled."
    : "See the evidence above; open questions are tracked in the repository.";
  dont.appendChild(dp);
  card.appendChild(dont);

  const reviewed = document.createElement("p");
  reviewed.className = "meta";
  reviewed.textContent = "Last reviewed: " + (claim.last_reviewed || "not yet reviewed") +
    " · Revision " + (claim.revision || 1);
  card.appendChild(reviewed);

  main.appendChild(card);
}

loadClaim();

/* Claims listing: keyword search + status filter. */

function matches(claim, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    claim.claim_text.toLowerCase().includes(q) ||
    (claim.search_text || "").includes(q) ||
    (claim.speaker || "").toLowerCase().includes(q) ||
    (claim.topic || "").toLowerCase().includes(q)
  );
}

async function loadClaims() {
  const container = document.getElementById("claims-list");
  const form = document.getElementById("claims-search");
  const qInput = document.getElementById("q");
  const statusSel = document.getElementById("status");

  const p = params();
  if (p.get("q")) qInput.value = p.get("q");
  if (p.get("status")) statusSel.value = p.get("status");

  const claims = await DATA.claims();

  function apply() {
    const q = qInput.value.trim();
    const status = statusSel.value;
    let list = claims.filter(c => matches(c, q));
    if (status) list = list.filter(c => c.status === status);
    renderClaimsInto(container, list, 0);
    if (!list.length) empty(container, "No claims match your search.");
  }

  form.addEventListener("submit", e => {
    e.preventDefault();
    apply();
  });
  statusSel.addEventListener("change", apply);
  apply();
}

loadClaims();

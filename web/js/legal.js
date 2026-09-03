/* International-law records page. */

const RECORD_TYPES = {
    allegation: "Allegation",
    provisional_measure: "Provisional measure",
    advisory_opinion: "Advisory opinion",
    judgment: "Judgment",
    arrest_warrant: "Arrest warrant",
    conviction: "Conviction",
    investigative_finding: "Investigative finding",
    political_resolution: "Political resolution",
};

function typePill(t) {
    const span = document.createElement("span");
    span.className = "status-pill " + t;
    span.textContent = RECORD_TYPES[t] || t;
    return span;
}

function recordCard(ld) {
    const el = document.createElement("article");
    el.className = "card legal-card";

    const h = document.createElement("h3");
    h.textContent = ld.body + " — " + ld.case_or_document;
    el.appendChild(h);

    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent =
        (ld.date || "undated") +
        (ld.jurisdiction ? " · " + ld.jurisdiction : "") +
        " · " + ld.id;
    el.appendChild(meta);

    el.appendChild(typePill(ld.document_type));

    const finding = document.createElement("div");
    finding.className = "evidence-block";
    const fh = document.createElement("h4");
    fh.textContent = "Finding";
    finding.appendChild(fh);
    const fp = document.createElement("p");
    fp.textContent = ld.finding;
    finding.appendChild(fp);
    el.appendChild(finding);

    const notEstablished = document.createElement("div");
    notEstablished.className = "evidence-block";
    const nh = document.createElement("h4");
    nh.textContent = "Does NOT establish";
    notEstablished.appendChild(nh);
    const np = document.createElement("p");
    np.textContent = ld.does_not_establish;
    notEstablished.appendChild(np);
    el.appendChild(notEstablished);

    if (ld.claims && ld.claims.length) {
        const related = document.createElement("p");
        related.className = "meta";
        related.textContent = "Related reviewed claims: " + ld.claims.join(", ");
        el.appendChild(related);
    }

    const reviewed = document.createElement("p");
    reviewed.className = "meta";
    reviewed.textContent = "Last reviewed: " + (ld.last_reviewed || "not yet reviewed");
    el.appendChild(reviewed);

    return el;
}

async function loadLegal() {
    const container = document.getElementById("legal-list");
    const form = document.getElementById("legal-search");
    const qInput = document.getElementById("q");
    const bodySel = document.getElementById("body");

    const records = await fetch("/data/legal.json").then(r => r.ok ? r.json() : []);

    function apply() {
        const q = qInput.value.trim().toLowerCase();
        const body = bodySel.value;
        let list = records;
        if (body) list = list.filter(ld => ld.body === body);
        if (q) {
            list = list.filter(ld =>
                (ld.case_or_document + " " + ld.finding + " " + ld.does_not_establish)
                    .toLowerCase().includes(q));
        }
        container.innerHTML = "";
        if (!list.length) {
            const p = document.createElement("p");
            p.className = "loading";
            p.textContent = "No published legal records yet.";
            container.appendChild(p);
            return;
        }
        list.forEach(ld => container.appendChild(recordCard(ld)));
    }

    form.addEventListener("submit", e => { e.preventDefault(); apply(); });
    bodySel.addEventListener("change", apply);
    apply();
}

loadLegal();

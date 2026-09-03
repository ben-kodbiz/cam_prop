/* Company detail page: relationships, timeline, statements. */

const REL_CLASSIFICATIONS = {
    documented_contract: "Documented contract",
    documented_service: "Documented service",
    reported_relationship: "Reported relationship",
    company_denial: "Company denial",
    company_confirmation: "Company confirmation",
    disputed: "Disputed",
    unknown: "Unknown",
    ended: "Ended",
    ongoing: "Ongoing",
};

function relPill(c) {
    const span = document.createElement("span");
    span.className = "status-pill " + c;
    span.textContent = REL_CLASSIFICATIONS[c] || c;
    return span;
}

function timelineList(timeline) {
    const block = document.createElement("div");
    block.className = "evidence-block";
    const h = document.createElement("h3");
    h.textContent = "Timeline";
    block.appendChild(h);
    if (!timeline || !timeline.length) {
        const p = document.createElement("p");
        p.textContent = "No recorded events yet.";
        block.appendChild(p);
        return block;
    }
    const ul = document.createElement("ul");
    ul.className = "timeline";
    timeline.forEach(e => {
        const li = document.createElement("li");
        const when = document.createElement("span");
        when.className = "when";
        when.textContent = e.date || "date unknown";
        li.appendChild(when);
        li.appendChild(document.createTextNode(" — "));
        const label = document.createElement("span");
        label.textContent = e.label;
        li.appendChild(label);
        ul.appendChild(li);
    });
    block.appendChild(ul);
    return block;
}

async function loadCompany() {
    const main = document.getElementById("company-page");
    const slug = new URLSearchParams(window.location.search).get("company");
    const rels = await fetch("/data/companies.json").then(r => r.ok ? r.json() : []);
    main.innerHTML = "";
    if (!slug) {
        const p = document.createElement("p");
        p.textContent = "No company specified.";
        main.appendChild(p);
        return;
    }
    const wanted = decodeURIComponent(slug).toLowerCase().replace(/-/g, " ");
    const entries = rels.filter(
        r => r.company.toLowerCase() === wanted ||
             r.company.toLowerCase().replace(/ /g, "-") === slug.toLowerCase()
    );
    if (!entries.length) {
        const p = document.createElement("p");
        p.textContent = "Company not found or no approved records published.";
        main.appendChild(p);
        return;
    }

    const h1 = document.createElement("h1");
    h1.textContent = entries[0].company;
    main.appendChild(h1);
    const intro = document.createElement("p");
    intro.textContent =
        "Documented relationships, company responses and open questions." +
        " The project documents what the evidence shows; it does not assume guilt or innocence.";
    main.appendChild(intro);

    entries.forEach(r => {
        const card = document.createElement("article");
        card.className = "card";
        const h = document.createElement("h3");
        h.textContent = r.service + " — customer: " + r.customer;
        card.appendChild(h);
        card.appendChild(relPill(r.classification));
        const meta = document.createElement("p");
        meta.className = "meta";
        meta.textContent =
            (r.start_date || "?") + (r.end_date ? " – " + r.end_date : "") +
            (r.confidence != null ? " · confidence " + Math.round(r.confidence * 100) + "%" : "");
        card.appendChild(meta);
        if (r.company_response) {
            const resp = document.createElement("p");
            resp.textContent = "Company response: " + r.company_response;
            card.appendChild(resp);
        }
        card.appendChild(timelineList(r.timeline));
        const reviewed = document.createElement("p");
        reviewed.className = "meta";
        reviewed.textContent = "Last reviewed: " + (r.last_reviewed || "not yet reviewed");
        card.appendChild(reviewed);
        main.appendChild(card);
    });
}

loadCompany();

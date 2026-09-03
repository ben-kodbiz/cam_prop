/* Companies page: documented relationships with links to detail pages. */

async function loadCompanies() {
    const container = document.getElementById("companies-list");
    const rels = await fetch("/data/companies.json").then(r => r.ok ? r.json() : []);
    container.innerHTML = "";
    if (!rels.length) {
        const p = document.createElement("p");
        p.className = "loading";
        p.textContent = "No corporate records published yet.";
        container.appendChild(p);
        return;
    }
    const byCompany = {};
    rels.forEach(r => {
        (byCompany[r.company] = byCompany[r.company] || []).push(r);
    });
    Object.keys(byCompany).sort().forEach(name => {
        const companyRels = byCompany[name];
        const el = document.createElement("article");
        el.className = "card";
        const h = document.createElement("h3");
        const a = document.createElement("a");
        a.href = "/company.html?company=" + encodeURIComponent(name.toLowerCase().replace(/ /g, "-"));
        a.textContent = name;
        h.appendChild(a);
        el.appendChild(h);
        companyRels.forEach(r => {
            const meta = document.createElement("p");
            meta.className = "meta";
            meta.textContent = r.service + " · Customer: " + r.customer;
            el.appendChild(meta);
            const cls = document.createElement("span");
            cls.className = "status-pill " + r.classification;
            cls.textContent = r.classification.replace(/_/g, " ");
            el.appendChild(cls);
            const dates = document.createElement("p");
            dates.className = "meta";
            dates.textContent = (r.start_date || "") + (r.end_date ? " – " + r.end_date : "");
            el.appendChild(dates);
            if (r.company_response) {
                const resp = document.createElement("p");
                resp.textContent = "Company response: " + r.company_response;
                el.appendChild(resp);
            }
        });
        container.appendChild(el);
    });
}

loadCompanies();

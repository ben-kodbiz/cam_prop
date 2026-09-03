/* Alternatives page: scores, migration guides, dependency mapping. */

async function loadAlternatives() {
    const container = document.getElementById("alternatives-list");
    const alternatives = await fetch("/data/alternatives.json").then(r => r.ok ? r.json() : []);
    container.innerHTML = "";
    if (!alternatives.length) {
        const p = document.createElement("p");
        p.className = "loading";
        p.textContent = "No alternatives published yet.";
        container.appendChild(p);
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
        byCategory[cat]
            .slice()
            .sort((x, y) => (y.score || 0) - (x.score || 0))
            .forEach(a => {
                const el = document.createElement("article");
                el.className = "card";
                const h3 = document.createElement("h3");
                if (a.alternative_url) {
                    const link = document.createElement("a");
                    link.href = a.alternative_url;
                    link.target = "_blank";
                    link.rel = "noopener";
                    link.textContent = a.alternative;
                    h3.appendChild(link);
                } else {
                    h3.textContent = a.alternative;
                }
                el.appendChild(h3);
                const meta = document.createElement("p");
                meta.className = "meta";
                meta.textContent = "Replaces: " + a.product +
                    (a.company ? " (" + a.company + ")" : "");
                el.appendChild(meta);

                const scoreLine = document.createElement("p");
                const score = a.score || 0;
                scoreLine.textContent = "Practicality score: " + score.toFixed(1) + " / 5";
                el.appendChild(scoreLine);

                const details = document.createElement("p");
                details.textContent =
                    (a.alternative_license ? "License: " + a.alternative_license + ". " : "") +
                    (a.self_hosting_available ? "Self-hosting available. " : "") +
                    (a.migration_difficulty
                        ? "Migration: " + a.migration_difficulty + ". " : "");
                el.appendChild(details);

                const guide = a.migration_guide;
                if (guide) {
                    const gblock = document.createElement("div");
                    gblock.className = "evidence-block";
                    const gh = document.createElement("h4");
                    gh.textContent = "Migration guide";
                    gblock.appendChild(gh);
                    const rows = [
                        ["Why choose it", guide.why_choose],
                        ["Data migration", guide.data_migration],
                        ["Installation difficulty", guide.installation_difficulty],
                        ["Limitations", guide.limitations],
                        ["Security & privacy", guide.security_considerations],
                    ];
                    rows.forEach(([label, value]) => {
                        if (!value) return;
                        const p = document.createElement("p");
                        p.textContent = label + ": " + value;
                        gblock.appendChild(p);
                    });
                    el.appendChild(gblock);
                }

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

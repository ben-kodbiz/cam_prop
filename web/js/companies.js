/* Companies page. */

async function loadCompanies() {
  const container = document.getElementById("companies-list");
  const companies = await DATA.companies();
  container.innerHTML = "";
  if (!companies.length) {
    empty(container, "No corporate records published yet.");
    return;
  }
  companies.forEach(c => {
    const el = document.createElement("article");
    el.className = "card";
    const h = document.createElement("h3");
    h.textContent = c.company;
    el.appendChild(h);
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = c.service + " · Customer: " + c.customer;
    el.appendChild(meta);
    const cls = document.createElement("p");
    cls.textContent = "Classification: " + c.classification.replace(/_/g, " ");
    el.appendChild(cls);
    if (c.company_response) {
      const resp = document.createElement("p");
      resp.textContent = "Company response: " + c.company_response;
      el.appendChild(resp);
    }
    const dates = document.createElement("p");
    dates.className = "meta";
    dates.textContent = (c.start_date || "") + (c.end_date ? " – " + c.end_date : "");
    el.appendChild(dates);
    container.appendChild(el);
  });
}

loadCompanies();

function renderProjectsRateCard(url, container) {
    // const allDedicatedURL = "{% url 'rate_cards:dedicated_services_all' %}"
    const header = `<thead><tr><th rowspan="2">#</th><th rowspan="2">Customer</th><th rowspan="2">Region</th><th rowspan="2">Country</th><th rowspan="2">Supplier</th><th rowspan="2">Currency</th><th rowspan="2">Entity</th><th rowspan="2">Payment</th><th colspan="5">Short Term (Up to 3 Months)</th><th colspan="5">Long Term (more than 3 Months) </th><th rowspan="2">Status</th><th rowspan="2">Action</th></tr><tr><th>Band 0</th><th>Band 1</th><th>Band 2</th><th>Band 3</th><th>Band 4</th><th>Band 0</th><th>Band 1</th><th>Band 2</th><th>Band 3</th><th>Band 4</th></tr></thead>`;

    // fetch()
    container.innerHTML = `<table>${header}<tbody></tbody></table>`
}

function renderDispatchRateCard(url, container) {
    // const allDedicatedURL = "{% url 'rate_cards:dedicated_services_all' %}"
    const header = `<thead><tr><th rowspan="2">#</th><th rowspan="2">Customer</th><th rowspan="2">Region</th><th rowspan="2">Country</th><th rowspan="2">Supplier</th><th rowspan="2">Currency</th><th rowspan="2">Entity</th><th rowspan="2">Payment</th><th colspan="6">Dispatch Tickets (incident) </th><th colspan="3">Dispatch Ticket (IMAC) </th><th rowspan="2">Status</th><th rowspan="2">Action</th></tr><tr><th>4 Hours</th><th>SBD</th><th>NBD</th><th>2 BD</th><th>3 BD</th><th>Additional Hour</th><th>2BD</th><th>3 BD</th><th>4 BD</th></tr></thead>`;

    // fetch()
    container.innerHTML = `<table>${header}<tbody></tbody></table>`
}

function renderScheduledRateCard(url, container) {
    // const allDedicatedURL = "{% url 'rate_cards:dedicated_services_all' %}"
    const header = `<thead><tr><th rowspan="2">#</th><th rowspan="2">Customer</th><th rowspan="2">Region</th><th rowspan="2">Country</th><th rowspan="2">Supplier</th><th rowspan="2">Currency</th><th rowspan="2">Entity</th><th rowspan="2">Payment</th><th colspan="3">Full Day Visit (8hrs)</th><th colspan="3">1/2 Day Visit (4hrs) </th><th rowspan="2">Status</th><th rowspan="2">Action</th></tr><tr><th>Band 0</th><th>Band 1</th><th>Band 2</th><th>Band 0</th><th>Band 1</th><th>Band 2</th></tr></thead>`;

    // fetch()
    container.innerHTML = `<table>${header}<tbody></tbody></table>`
}


function renderDedicatedRateCard(url, container) {
    // const allDedicatedURL = "{% url 'rate_cards:dedicated_services_all' %}"
    const header = `<thead><tr><th rowspan="2">#</th><th rowspan="2">Customer</th><th rowspan="2">Region</th><th rowspan="2">Country</th><th rowspan="2">Supplier</th><th rowspan="2">Currency</th><th rowspan="2">Entity</th><th rowspan="2">Payment</th><th colspan="2">Band 0</th><th colspan="2">Band 1</th><th colspan="2">Band 2</th><th colspan="2">Band 3</th><th colspan="2">Band 4</th><th rowspan="2">Status</th><th rowspan="2">Action</th></tr><tr><th>With</th><th>Without</th><th>With</th><th>Without</th><th>With</th><th>Without</th><th>With</th><th>Without</th><th>With</th><th>Without</th></tr></thead>`;

    fetch(url).then(val => val.json()).then(val => console.log(val)).catch(e => console.log(e));
    container.innerHTML = `<table>${header}<tbody></tbody></table>`
}

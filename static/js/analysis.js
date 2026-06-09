fetch(`/api/analysis/${NODE}`)
    .then(r => r.json())
    .then(data => {

        new Chart(document.getElementById("flowChart"), {
            type: "line",
            data: {
                labels: data.hours,
                datasets: [{
                    label: "Flujo",
                    data: data.flow
                }]
            }
        });

        new Chart(document.getElementById("impactChart"), {
            type: "bar",
            data: {
                labels: data.impact.map(d => d.street),
                datasets: [{
                    label: "Impacto %",
                    data: data.impact.map(d => d.value)
                }]
            }
        });

    });
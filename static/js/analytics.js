fetch("/api/analytics")

.then(r => r.json())

.then(data => {

    if(data.mode === "street") {

        document
        .getElementById(
            "streetTitle"
        )
        .innerHTML =
        `<h3>${data.street}</h3>`;

        new Chart(
            document.getElementById(
                "flowChart"
            ),
            {
                type:"line",
                data:{
                    labels:data.labels,
                    datasets:[{
                        label:"Flow",
                        data:data.flow
                    }]
                }
            }
        );

        new Chart(
            document.getElementById(
                "congestionChart"
            ),
            {
                type:"bar",
                data:{
                    labels:[
                        data.street
                    ],
                    datasets:[{
                        label:"Congestion",
                        data:[
                            data.congestion
                        ]
                    }]
                }
            }
        );

        document
        .getElementById(
            "insights"
        )
        .innerHTML = `

        <h3>Insights</h3>

        <p>
        Length:
        ${data.length} m
        </p>

        <p>
        Congestion:
        ${data.congestion}x
        </p>

        `;
    }

    else {

        new Chart(
            document.getElementById(
                "flowChart"
            ),
            {
                type:"line",
                data:{
                    labels:data.labels,
                    datasets:[{
                        label:
                        "Valencia Traffic",
                        data:data.flow
                    }]
                }
            }
        );

        document
        .getElementById(
            "insights"
        )
        .innerHTML = `

        <h3>City Overview</h3>

        <p>
        Average congestion:
        ${data.average_congestion}
        </p>

        <p>
        Closed streets:
        ${data.closed_streets}
        </p>

        `;
    }

});
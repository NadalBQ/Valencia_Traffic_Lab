const slider =
    document.getElementById("hour");

const label =
    document.getElementById("hourLabel");

slider.addEventListener(
    "input",
    () => {

        label.innerText =
            slider.value.padStart(2, "0")
            + ":00";

        fetch("/api/set_hour", {

            method: "POST",

            headers: {
                "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
                hour: slider.value
            })

        })
        .then(() => {
            loadMap();
        });

    }
);
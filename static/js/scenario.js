const slider = document.getElementById("hour");
const label = document.getElementById("hourLabel");

slider.addEventListener("input", () => {

    label.innerText = slider.value + ":00";

    fetch("/api/state")
        .then(r => r.json())
        .then(() => {
            // el backend ya recalcula flujos
            window.dispatchEvent(new Event("reload-map"));
        });
});
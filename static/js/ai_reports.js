document.addEventListener(
    "DOMContentLoaded",
    () => {
        const page =
            document.getElementById(
                "aiReportsPage"
            );

        const form =
            document.getElementById(
                "generateReportForm"
            );

        const button =
            document.getElementById(
                "generateReportButton"
            );


        if (
            page
            && page.dataset.autoRefresh
            === "true"
        ) {
            window.setTimeout(
                () => {
                    window.location.reload();
                },
                3000
            );
        }


        if (form) {
            form.addEventListener(
                "submit",
                () => {
                    if (!button) {
                        return;
                    }

                    button.disabled = true;

                    const label =
                        button.querySelector(
                            "span"
                        );

                    if (label) {
                        label.textContent =
                            "Queuing...";
                    }
                }
            );
        }
    }
);
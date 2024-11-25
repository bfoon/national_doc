const userData = {
    nationalId: {
        appointment: {
            date: "",
            time: "",
            type: "National ID Card Interview",
            name: "",
            queueNumber: "",
            token: ""
        }
    },
    residentPermit: {
        appointment: {
            date: "",
            time: "",
            type: "Resident Permit Interview",
            name: "",
            queueNumber: "",
            token: ""
        }
    },
    workPermit: {
        appointment: {
            date: "",
            time: "",
            type: "Work Permit Interview",
            name: "",
            queueNumber: "",
            token: ""
        }
    }
};

// Function to set the appointment data
function setAppointmentData(serviceType, data) {
    if (userData[serviceType]) {
        userData[serviceType].appointment.date = data.date;
        userData[serviceType].appointment.time = data.time;
        userData[serviceType].appointment.name = data.name;
        userData[serviceType].appointment.queueNumber = data.queueNumber;
        userData[serviceType].appointment.token = data.token;
    } else {
        console.error(`Service type "${serviceType}" not recognized.`);
    }
}

// Function to print appointment details with QR code
function printAppointment(applicationType) {
    const appointment = userData[applicationType]?.appointment;

    if (!appointment || !appointment.token) {
        alert("No appointment data available for this service or token is missing.");
        return;
    }

    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
        <head>
            <title>Appointment Details</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    margin: 0;
                    padding: 20px;
                    background-color: #f9f9f9;
                }
                .appointment-container {
                    border: 1px solid #ccc;
                    padding: 20px;
                    width: 400px;
                    background-color: #fff;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    text-align: center;
                    margin: auto;
                }
                .appointment-details {
                    margin-bottom: 20px;
                }
                .qrcode-container {
                    margin: 20px 0;
                }
                #qrcode {
                    display: inline-block;
                }
                h2 {
                    font-size: 1.5em;
                    margin-bottom: 10px;
                    color: #333;
                }
                p {
                    margin: 5px 0;
                    font-size: 1em;
                    color: #555;
                }
                strong {
                    color: #000;
                }
            </style>
        </head>
        <body>
            <div class="appointment-container">
                <h2>${appointment.type}</h2>
                <div class="appointment-details">
                    <p><strong>Date:</strong> ${appointment.date}</p>
                    <p><strong>Time:</strong> ${appointment.time}</p>
                    <p><strong>Queue Number:</strong> ${appointment.queueNumber}</p>
                    <p><strong>Applicant:</strong> ${appointment.name}</p>
                    <p><strong>Token:</strong> ${appointment.token}</p>
                </div>
                <div class="qrcode-container">
                    <div id="qrcode"></div>
                </div>
                <p>Please bring this appointment slip and all required documents to your interview.</p>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
            <script>
                // Generate the QR code with the appointment token
                new QRCode(document.getElementById("qrcode"), {
                    text: "${appointment.token}",
                    width: 120,
                    height: 120,
                    colorDark: "#000000",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.H
                });
            </script>
        </body>
        </html>
    `);
    printWindow.document.close();

    // Wait for QR code rendering before triggering print
    setTimeout(() => {
        printWindow.print();
    }, 500);
}


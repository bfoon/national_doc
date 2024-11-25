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
                    margin: 20px;
                }
                h1 {
                    color: #3498db;
                    text-align: center;
                }
                .appointment-container {
                    border: 1px solid #ccc;
                    padding: 20px;
                    width: 100%;
                    max-width: 600px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    position: relative;
                    margin-top: 20px;
                }
                .appointment-details, .qrcode-container {
                    display: inline-block;
                    vertical-align: top;
                }
                .appointment-details {
                    width: 70%;
                }
                .qrcode-container {
                    width: 25%;
                    text-align: center;
                }
                #qrcode {
                    margin-top: 10px;
                    display: inline-block;
                }
            </style>
        </head>
        <body>
            <h1>National Document Portal - Appointment Details</h1>
            <div class="appointment-container">
                <div class="appointment-details">
                    <h2>${appointment.type}</h2>
                    <p><strong>Date:</strong> ${appointment.date}</p>
                    <p><strong>Time:</strong> ${appointment.time}</p>
                    <p><strong>Queue Number:</strong> ${appointment.queueNumber}</p>
                    <p><strong>Applicant:</strong> ${appointment.name}</p>
                    <p><strong>Token:</strong> ${appointment.token}</p>
                    <p>Please bring this appointment slip and all required documents to your interview.</p>
                </div>
                <div class="qrcode-container">
                    <div id="qrcode"></div>
                    <p>Scan for Details</p>
                </div>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
            <script>
                // Generate the QR code with the appointment token
                new QRCode(document.getElementById("qrcode"), {
                    text: "${appointment.token}",
                    width: 100,
                    height: 100,
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

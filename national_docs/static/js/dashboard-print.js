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
    },
    // Add any other services as needed...
};

// Function to set the appointment data
function setAppointmentData(serviceType, data) {
    userData[serviceType].appointment.date = data.date;
    userData[serviceType].appointment.time = data.time;
    userData[serviceType].appointment.name = data.name;
    userData[serviceType].appointment.queueNumber = data.queueNumber;
    userData[serviceType].appointment.token = data.token;
}

// Function to print appointment details
function printAppointment(applicationType) {
    const appointment = userData[applicationType].appointment; // Get the specific appointment data

    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
        <head>
            <title>Appointment Details</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                h1 { color: #3498db; }
                .appointment-details { border: 1px solid #ccc; padding: 20px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>National Document Portal - Appointment Details</h1>
            <div class="appointment-details">
                <h2>${appointment.type}</h2>
                <p><strong>Date:</strong> ${appointment.date}</p>
                <p><strong>Time:</strong> ${appointment.time}</p>
                <p><strong>Queue Number:</strong> ${appointment.queueNumber}</p>
                <p><strong>Applicant:</strong> ${appointment.name}</p>
                <p><strong>Token:</strong> ${appointment.token}</p>
            </div>
            <p>Please bring this appointment slip and all required documents to your interview.</p>
        <div class="qrcode" id="qrcode"></div>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
            <script>
                // Generate the QR code with the appointment token
                new QRCode(document.getElementById("qrcode"), {
                    text: "${appointment.token}",  // Use appointment.token as the QR code content
                    width: 100,
                    height: 100,
                    colorDark : "#000000",
                    colorLight : "#ffffff",
                    correctLevel : QRCode.CorrectLevel.H
                });
            </script>
        </body>
        </html>
    `);
    printWindow.document.close();
    printWindow.print();
}

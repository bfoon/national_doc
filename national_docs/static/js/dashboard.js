let applicationId;  // To store the application ID globally

$(document).ready(function() {
    $('#applicationModal').on('show.bs.modal', function (event) {
        const button = $(event.relatedTarget);
        applicationId = button.data('application-id');  // Store application ID when the modal opens
        const applicationType = button.data('application-type');

        const fetchUrl = button.data('fetch-url');  // Pass the URL from the template

        // AJAX request to fetch the application details
        $.ajax({
            url: fetchUrl,  // Dynamic URL passed from the template
            data: {
                'application_id': applicationId,
                'application_type': applicationType
            },
            success: function(response) {
                $('#applicationDetails').html(response.html);

                // Show immigration note if available
                if (response.immigration_note) {
                    $('#immigrationNote').show();
                    $('#immigrationMessage').text(response.immigration_note);
                } else {
                    $('#immigrationNote').hide();
                }

                // Show or hide cancel button based on response
                if (response.allow_cancel) {
                    $('#cancelApplicationBtn').show();
                } else {
                    $('#cancelApplicationBtn').hide();
                }
            }
        });
    });

    // Handle Cancel Application button click event
    $('#cancelApplicationBtn').click(function() {
        const cancelUrl = $(this).data('cancel-url');  // Pass the URL from the template
        if (applicationId) {
            // AJAX request to cancel the application
            $.ajax({
                url: cancelUrl,  // Dynamic URL passed from the template
                data: {
                    'application_id': applicationId
                },
                success: function(response) {
                    if (response.success) {
                        alert('Application successfully cancelled.');
                        $('#applicationModal').modal('hide');
                        location.reload();  // Reload the page to reflect the cancellation
                    } else {
                        alert(response.error);
                    }
                },
                error: function(xhr, status, error) {
                    alert('Error cancelling the application: ' + error);
                }
            });
        }
    });
});

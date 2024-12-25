document.addEventListener('DOMContentLoaded', function () {
        // Function to setup file upload
        function setupFileUpload(uploadAreaId, fileInputId, fileNameDisplayId) {
            const uploadArea = document.getElementById(uploadAreaId);
            const fileInput = document.getElementById(fileInputId);
            const fileNameDisplay = document.getElementById(fileNameDisplayId);

            uploadArea.addEventListener('click', () => fileInput.click());
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('border-primary');
            });
            uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('border-primary'));
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('border-primary');
                fileInput.files = e.dataTransfer.files;
                fileNameDisplay.textContent = `Selected: ${e.dataTransfer.files[0].name}`;
            });
            fileInput.addEventListener('change', () => {
                if (fileInput.files.length > 0) {
                    fileNameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
                }
            });
        }

        // Setup file upload handlers
        setupFileUpload('birth-certificate-upload', 'birth-certificate', 'birth-certificate-file-name');
        setupFileUpload('passport-photo-upload', 'passport-photo', 'passport-photo-file-name');

        // Custom validation messages
        const validationMessages = {
            fullName: {
                pattern: 'Please enter your full name (at least two names)',
                required: 'Full name is required'
            },
            dateOfBirth: {
                age: 'You must be at least 18 years old',
                required: 'Date of birth is required'
            },
            phone: {
                pattern: 'Please enter a valid phone number',
                required: 'Phone number is required'
            },
            email: {
                pattern: 'Please enter a valid email address',
                required: 'Email address is required'
            },
            birthCertificate: {
                size: 'File size must be less than 5MB',
                type: 'Only PDF, JPG, and PNG files are allowed',
                required: 'Birth certificate is required'
            },
            passportPhoto: {
                size: 'File size must be less than 2MB',
                type: 'Only JPG and PNG files are allowed',
                required: 'Passport photo is required'
            }
        };

        // Validation functions
        const validators = {
            fullName: (value) => value.trim().split(' ').length >= 2,
            dateOfBirth: (value) => {
                const birthDate = new Date(value);
                const today = new Date();
                let age = today.getFullYear() - birthDate.getFullYear();
                const monthDiff = today.getMonth() - birthDate.getMonth();
                if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
                    age--;
                }
                return age >= 18;
            },
            phone: (value) => /^(\+220|00220)?[567]\d{7}$/.test(value.replace(/\s/g, '')),
            email: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
            file: (file, maxSize, allowedTypes) => {
                if (!file) return { valid: false, message: 'File is required' };
                const fileSize = file.size / 1024 / 1024;
                const fileType = file.type.toLowerCase();
                if (fileSize > maxSize) {
                    return { valid: false, message: `File size must be less than ${maxSize}MB` };
                }
                if (!allowedTypes.includes(fileType)) {
                    return { valid: false, message: `Only ${allowedTypes.join(', ')} files are allowed` };
                }
                return { valid: true };
            }
        };

        // Handle file uploads
        function handleFileUpload(input, fileNameElement, maxSize, allowedTypes) {
            const file = input.files[0];
            const fileNameDisplay = document.getElementById(fileNameElement);

            if (file) {
                const validation = validators.file(file, maxSize, allowedTypes);
                if (validation.valid) {
                    fileNameDisplay.textContent = file.name;
                    fileNameDisplay.className = 'file-name text-success mt-2';
                } else {
                    fileNameDisplay.textContent = validation.message;
                    fileNameDisplay.className = 'file-name text-danger mt-2';
                }
            } else {
                fileNameDisplay.textContent = '';
            }
        }

        document.getElementById('birth-certificate').addEventListener('change', function () {
            handleFileUpload(this, 'birth-certificate-file-name', 5, ['application/pdf', 'image/jpeg', 'image/png']);
        });

        document.getElementById('passport-photo').addEventListener('change', function () {
            handleFileUpload(this, 'passport-photo-file-name', 2, ['image/jpeg', 'image/png']);
        });

        // Form validation
        const form = document.getElementById('national-id-form');
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            let isValid = true;
            form.querySelectorAll('input, select, textarea').forEach(input => {
                if (input.id === 'full-name' && !validators.fullName(input.value)) {
                    isValid = false;
                }
                if (input.id === 'date-of-birth' && !validators.dateOfBirth(input.value)) {
                    isValid = false;
                }
                if (!isValid) input.classList.add('is-invalid');
            });

            if (isValid) {
                const disclaimerModal = new bootstrap.Modal(document.getElementById('disclaimerModal'));
                disclaimerModal.show();

                document.getElementById('confirmDisclaimer').addEventListener('click', function () {
                    disclaimerModal.hide();
                    form.submit();
                });
            }
        });
    });
# Welcome to Coruscant Health Administration
***
## Task
The task was to rebuild the Medical Management System of the Coruscant Health Administration (CHA), the organization responsible for the health care of Coruscant's citizens and for running its medcenters.
The project had to be written in Python with the Django framework, use a database, have a clean and easy-to-use interface, include unit tests, use CI/CD and be hosted in the cloud, with the URL written in `my_coruscant_health_administration_url.txt`.
The system has five stakeholders, and each one needed its own features:
Patient: registers with the acknowledgment of the administrator, uploads the data collected by a device attached to the body, views the health readings and views the suggestions prescribed by the doctor.
Doctor: registers with the acknowledgment of the administrator, views the uploaded patient records, monitors whether the patient's condition is improving, writes a report with a prescription and orders services such as a CT scan or PET scan.
Department: receives the orders, executes them and uploads the results.
Administrator: stores patient and doctor details during registration, creates the database tables, upgrades and monitors the application.
Emergency Services: adds each new patient quickly and efficiently.
In addition, patients and doctors must be able to upload documents, and these documents must be encrypted and stored according to the latest security standard.

## Description
I built the project with Django 5.2 and split it into two apps. The `accounts` app contains a custom `User` model with a `role` field (patient, doctor, department, emergency, admin) and an `is_approved` field. A custom `role_required` decorator checks on every page that the user is logged in, approved by the administrator and has the right role; otherwise the user is redirected to a waiting page or gets a "403 Forbidden" error.
The `clinic` app contains the medical data: `Patient`, `Reading` (heart rate, blood pressure, temperature, oxygen), `Report`, `Order`, `Document` and `Message` models. Patients can import device data from a CSV file, which I read with Python's `csv` module, or add a reading by hand. Every reading is compared with normal adult ranges and abnormal values are shown in red. To show whether a patient is improving, the `status()` method compares the number of abnormal values in the last three readings with the three readings before them.
When a doctor orders a service, the order is automatically sent to the correct department (for example a CT scan goes to Radiology and a blood test goes to the Laboratory). Department staff only see the orders of their own department, start them and upload the result together with an optional file.
Uploaded documents are encrypted with AES-256-GCM from the `cryptography` library. Each file gets a new random nonce, only the encrypted bytes are saved in the database, and GCM also detects if the stored data has been changed. The encryption key is kept in an environment variable on the server, not in the code.
The database is PostgreSQL in production and SQLite on a local computer, and the tables are created with Django migrations. I wrote 22 unit tests with Django's test framework that cover registration and approval, permissions, CSV upload, the improving/worsening logic, orders, emergency intake and document encryption. For CI/CD I used GitHub Actions: on every push the code is checked with Ruff, the tests run against a PostgreSQL database, and if everything passes the application is deployed to Render and the `/health/` page is checked to confirm the site is running. The interface is built with Django templates and a single CSS file.
## Installation
No installation is needed to view the finished project. It is already deployed on Render, and the address is written in the `my_coruscant_health_administration_url.txt` file, so it can be opened directly in any web browser. On the free plan the site goes to sleep when nobody uses it, so the first page may take up to a minute to load.
To run the project on your own computer, you need Python 3.12 or newer and Git. First download the repository with Git and open the project folder in a terminal. Then install the required packages listed in the `requirements.txt` file with pip (or `requirements-dev.txt` if you also want the code checker). After that, create the database tables with Django's `migrate` command and fill the database with demo users and example data with the `seed_cha --demo` command. No separate database server is needed locally, because the project automatically uses an SQLite file when no PostgreSQL address is given.

## Usage
Open the site in a web browser. The login page lists the demo accounts, and all of them use the password `Coruscant-22BBY`: `admin` (administrator), `doctor` (doctor), `patient` (patient), `radiology` and `lab` (department staff) and `emergency` (emergency services). New users can create an account with the "Register here" link, but they can only use the system after the administrator approves them.
As a patient you can see your readings, upload a CSV file from your device (an example is included in `sample_device_data.csv`), add a reading by hand, read the doctor's reports, follow your tests and scans, send messages to the doctor and upload documents.
As a doctor you open the Patients page, choose a patient, look at the readings and condition, write a report with a prescription and order a service from a department.
As department staff you see the orders sent to your department, start them and upload the result.
As emergency services you add a new patient with just a name, the complaint and a priority, and the list is sorted with the most critical patients first.
As the administrator you approve or reject new registrations on the Administration page, see statistics about the system and manage all data through the Database (Django admin) link.
To run the project locally, start Django's development server with the `runserver` command and open the address it shows (usually http://127.0.0.1:8000) in the browser. The unit tests can be run at any time with Django's `test` command.

### The Core Team
abdullaz_a
<span><i>Made at <a href='https://qwasar.io'>Qwasar SV -- Software Engineering School</a></i></span>
<span><img alt='Qwasar SV -- Software Engineering School's Logo' src='https://storage.googleapis.com/qwasar-public/qwasar-logo_50x50.png' width='20px' /></span>
# Google Play App Scraper

This is a simple Flask web application that allows you to get download statistics for any app on the Google Play Store.

## Features

-   **Public Search**: Enter any app name to get its current Google Play Store statistics.
-   **Protected Log Page**: A password-protected page (`/log`) to view and manage statistics for a specific app ("Deerwalk Learning Center").

## Log Monitoring

This application includes a password-protected area for monitoring app logs.

-   **URL**: `/log`
-   **Password**: `dss`

On this page, you can:
-   View all historical log entries.
-   Manually trigger a new log entry to be saved.
-   Delete all logs.

## Local Development

To run this application on your local machine, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    flask run
    ```
    The application will be available at `http://127.0.0.1:5000`.

## Deployment on Render

This application is configured for deployment on [Render](https://render.com/).

1.  **Fork this repository** to your GitHub account.
2.  Go to the [Render Dashboard](https://dashboard.render.com/) and create a **New Web Service**.
3.  Connect your GitHub account and select the forked repository.
4.  Render will automatically detect the `render.yaml` file and configure the service.
5.  Click **Create Web Service** to deploy the application.

The application will be deployed to a public URL.

### Important Note on Data Persistence

This application writes its log file (`deerwalk_logs.jsonl`) to the local filesystem of the server. Free services on Render have an **ephemeral filesystem**, which means the log file will be **deleted** every time the application restarts or is redeployed.

For a production environment where you need to keep your logs permanently, you should use **Render Disks**, which is a paid feature that provides persistent storage. You can learn more in the [Render documentation on disks](https://render.com/docs/disks).

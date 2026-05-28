# StudySmart

A smart study planner that builds your revision schedule automatically based on your exam dates and availability.

## Features
- Input your exams with dates and estimated study hours
- Set daily available study hours and commitments
- Import commitments automatically from Google Calendar
- Edit commitments inside the planner 
- Get an automatically generated color coded study schedule
- Receive warnings when there is not enough time for an exam
- Export study schedule to Google Calendar
- Get personalised study tips based on psychology research
- Optional: spaced repetition schedule based on the Ebbinghaus forgetting curve

## Installation
```bash
pip install -e .
```

## Usage
```bash
python src/study_smart/app.py
```

## Documentation

To view the documentation for schedule.py, run:

```bash
pdoc --docformat google src/study_smart/schedule.py
```

To view the documentation for google_calendar.py, run:

```bash
pdoc --docformat google src/study_smart/google_calendar.py
```

## Testing

To run the unit tests:

```bash
pytest tests/
```

To run tests with coverage report:

```bash
pytest --cov=study_smart tests/
```

## Google Calendar Integration

To use the Google Calendar import and export feature, you need to set up your own Google OAuth credentials:

1. Go to Google Cloud Console (https://console.cloud.google.com)
2. Create a new project
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download the credentials as `credentials.json`
6. Place `credentials.json` in the root of the repository
7. On first run, a browser window will open asking you to grant calendar access

Note: `credentials.json` and `token.json` are excluded from version control for security reasons.

## Google Calendar Setup

StudySmart can import your existing calendar events as commitments and export your study schedule back to Google Calendar. This feature is optional — the app works fully without it.

Note: This setup only needs to be done once. After the first authentication, `token.json` is created automatically and you won't need to repeat these steps.

### Step 1 — Create a Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in with your Google account
2. Click the project dropdown at the top left → **New Project**
3. Give it a name (`StudySmart`) → click **Create**
4. Wait a moment for the project to be created, then make sure it is selected in the dropdown at the top

### Step 2 — Enable the Google Calendar API

1. In the left sidebar go to **APIs & Services** → **Library**
2. Search for **Google Calendar API**
3. Click on it → click **Enable**

### Step 3 — Configure the OAuth consent screen

1. In the left sidebar go to **APIs & Services** → **OAuth consent screen**. On newer versions of Google Cloud Console this may appear as **Google Auth Platform** → **Audience** under project configuration
2. Choose **External** as user type → click **Create**
3. Fill in the required fields:
   - **App name**: StudySmart
   - **User support email**: your Gmail address
   - **Developer contact email**: your Gmail address
4. Click **Save and Continue** through the **Scopes** step — no changes needed here
5. Go to **Audience** → scroll down to **Test users** → click **Add users** → add your Gmail address → click **Add**
6. Click **Save and Continue** → **Back to Dashboard**

> 💡 You must add your own Gmail as a test user — otherwise Google will block authentication with an "access denied" error even though you created the project.

### Step 4 — Create OAuth credentials

1. In the left sidebar go to **APIs & Services** → **Credentials** (use the search bar at the top if you can't find it)
2. Click **Create credentials** → **OAuth Client ID**
3. Choose **Desktop app** as application type
4. Give it a name (e.g. `StudySmart Desktop`) → click **Create**
5. A popup will appear — click **Download JSON**
6. Rename the downloaded file to exactly `credentials.json`
7. Place `credentials.json` in the root of the StudySmart repository (the same folder as `pyproject.toml`)

### Step 5 — First time authentication

1. Run the app from the repo root:
```bash
cd path/to/StudySmart
python src/study_smart/app.py
```
2. Add your exams in the **📚 My Exams** tab
3. Go to **⏰ My Schedule** tab → click **📅 Import from Google Calendar**
4. A browser window will open asking you to sign in with Google — select your Google account
5. You will see a warning: **"Google hasn't verified this app"** — this is expected! Click **Continue** → **Go to StudySmart (unsafe)**. This warning appears because the app is in testing mode and has not gone through Google's full verification process, which is designed for apps published to the general public. For a personal locally-run study tool, testing mode is completely safe.
6. Click **Allow** to grant calendar access
7. The browser will show a success message — you can close the browser tab and return to the app
8. A `token.json` file is automatically created in the repo root — this stores your authentication so you won't need to log in again next time


## Study Tips
Hard-coded tips, based on psychological research.


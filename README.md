# StudySmart

A smart study planner that builds your revision schedule automatically based on your exam dates and availability.

## Features
- Input your exams with dates and estimated study hours
- Set daily available study hours and commitments
- Import commitments automatically from Google Calendar
- Edit/ commitments inside the planner 
- Get an automatically generated color coded revision schedule
- Receive warnings when there is not enough time for an exam
- Get personalised study tips based on psychology research
- Optional spaced repetition schedule based on the Ebbinghaus forgetting curve

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

To use the Google Calendar import feature, you need to set up your own Google OAuth credentials:

1. Go to Google Cloud Console (https://console.cloud.google.com)
2. Create a new project
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download the credentials as `credentials.json`
6. Place `credentials.json` in the root of the repository
7. On first run, a browser window will open asking you to grant calendar access

Note: `credentials.json` and `token.json` are excluded from version control for security reasons.

## Study Tips
Hard-coded tips, based on psychological research.


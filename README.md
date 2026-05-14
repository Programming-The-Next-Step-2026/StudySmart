# StudySmart

A smart study planner that builds your revision schedule automatically based on your exam dates and availability.

## Features
- Input your exams with dates, difficulty and estimated study hours
- Set daily available study hours
- Get an automatically generated revision schedule
- Receive warnings when schedule is overloaded
- Receive study tips based on the schedule

## Documentation

To view the documentation, run:

```bash
pdoc --docformat google src/study_smart/schedule.py
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


import os
from dash import Dash, html, dcc, Input, Output, State, ALL, ctx
import dash
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
from study_smart.schedule import build_schedule, generate_tips


app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], suppress_callback_exceptions=True)

# store exams and commitments in memory
exams = []
commitments = {}
commitment_names = []

app.layout = dbc.Container([
    html.H1("StudySmart", className="my-4"),
    dcc.Store(id="schedule-store"),
    dcc.Store(id="spaced-repetition-store"),
    dcc.Store(id="start-date-store"),
    dcc.Store(id="current-week-store", data=0),
    dcc.Store(id="color-map-store"),
    dcc.Store(id="exam-colors-store"),

    dcc.Tabs([

        # Tab 1 - My Exams
        dcc.Tab(label="📚 My Exams", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("Add an exam", className="mt-4"),
                    dbc.Label("Exam name"),
                    dbc.Input(id="exam-name", placeholder="e.g. Statistics", type="text"),
                    dbc.Label("Exam date", className="mt-2"),
                    dcc.DatePickerSingle(id="exam-date", date=str(date.today())),
                    dbc.Label("Hours needed", className="mt-2"),
                    dbc.Input(id="exam-hours", type="number", min=1, max=100, placeholder="e.g. 20"),
                    dbc.Label("Topics (optional, comma separated)", className="mt-2"),
                    dbc.Input(id="exam-topics", placeholder="e.g. Chapter 1, Chapter 2, Chapter 3", type="text"),
                    dbc.Button("Add exam", id="add-exam-button", color="primary", className="mt-3"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col(dbc.Button("💾 Save", id="save-button", color="secondary", size="sm")),
                        dbc.Col(dbc.Button("📂 Load", id="load-button", color="secondary", size="sm")),
                          dbc.Col(html.Div(id="save-status"), width="auto"), 
                    ], className="mb-3"),
                    html.Div(id="exam-table")
                ], width=6)
            ])
        ]),

        # Tab 2 — My Schedule
        dcc.Tab(label="⏰ My Schedule", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("Schedule settings", className="mt-4"),
                    dbc.Label("Default study hours per day"),
                    dbc.Input(id="default-hours", type="number", min=1, max=16, value=7),
                    dbc.Label("Start studying from", className="mt-2"),
                    dcc.DatePickerSingle(id="start-date", date=str(date.today())),
                    html.Hr(),
                    html.H5("Add a commitment", className="mt-3"),
                    dbc.Label("Date"),
                    dcc.DatePickerSingle(id="commitment-date", date=str(date.today())),
                    dbc.Label("What", className="mt-2"),
                    dbc.Input(id="commitment-name", placeholder="e.g. Lecture", type="text"),
                    dbc.Label("Hours blocked", className="mt-2"),
                    dbc.Input(id="commitment-hours", type="number", min=1, max=16, placeholder="e.g. 2"),
                    dbc.Button("Add commitment", id="add-commitment-button", color="primary", className="mt-3"),
                    html.Hr(),
                    dbc.Button("📅 Import from Google Calendar", id="import-calendar-button", color="info", className="mb-3"),
                    html.Div(id="commitment-list")
                ], width=6)
            ])
        ]),

        # Tab 3 — Study Plan
        dcc.Tab(label="🗓️ Study Plan", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("Study Plan", className="mt-4"),
                    dbc.Checklist(
                        id="spaced-repetition-toggle",
                        options=[{"label": " Use spaced repetition (Ebbinghaus)", "value": "on"}],
                        value=[],
                        className="mt-2"
                    ),
                    dbc.Button("Generate / Regenerate schedule", id="generate-button", color="success", className="mt-3 mb-3"),
                    dbc.Button("📅 Export to Google Calendar", id="export-calendar-button", color="info", className="mt-3 mb-3"),
                    html.Div(id="export-calendar-status"),
                    html.Div(id="warnings-div"),
                    dcc.Graph(id="schedule-chart"),
                    html.Div(id="legend-div"),
                    html.H5("Weekly view", className="mt-4"),
                    html.Div(id="schedule-list"),
                    html.H5("Study tips", className="mt-4"),
                    html.Div(id="tips-div"),
                ], width=10)
            ])
        ]),

    ])
], fluid=True)


def get_subject_color_map(schedule, exam_list):
    """Assign one color per exam — all topics of same exam share color."""
    exam_names = [e["name"] for e in exam_list]
    n = max(len(exam_names), 1)

    # color per exam
    exam_colors = {}
    for i, exam_name in enumerate(exam_names):
        hue = int((i / n) * 360)
        exam_colors[exam_name] = f"hsl({hue}, 70%, 50%)"

    # map each topic AND exam name to its exam color
    color_map = {}
    for e in exam_list:
        color = exam_colors[e["name"]]
        color_map[e["name"]] = color
        for t in e["topics"]:  # ← use original topic names, no prefix
            color_map[t] = color

    return color_map, exam_colors

def build_chart(schedule, spaced, color_map):
    """Build Plotly bar chart from schedule DataFrame."""
    schedule_plot = schedule.copy()
    schedule_plot["date"] = schedule_plot["date"].apply(str)
    # strip exam prefix for display in chart legend
    schedule_plot["display_subject"] = schedule_plot["subject"].apply(
        lambda s: s.split(": ", 1)[-1] if ": " in s else s
    )
    return px.bar(
        schedule_plot,
        x="date",
        y="hours",
        color="subject",
        color_discrete_map=color_map,
        pattern_shape="type" if spaced else None,
        title="Study Schedule",
        labels={"hours": "Hours", "date": "Date", "subject": "Subject"}
    )


def build_weekly_view(schedule, spaced, week_offset=0, color_map=None, exam_colors=None):
    """Build weekly calendar view from schedule DataFrame."""
    if schedule.empty:
        return html.P("No schedule yet.")

    all_dates = sorted(schedule["date"].unique())
    if not all_dates:
        return html.P("No schedule yet.")

    if not color_map:
        color_map = {}
    if not exam_colors:
        exam_colors = {}

    # find start of first week (Monday)
    first_date = all_dates[0]
    days_since_monday = first_date.weekday()
    week_start = first_date - timedelta(days=days_since_monday)

    # apply week offset
    week_start = week_start + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    # build legend
    legend_items = []
    for exam_name, color in exam_colors.items():
        legend_items.append(
            html.Span([
                html.Span(style={
                    "display": "inline-block",
                    "width": "12px",
                    "height": "12px",
                    "borderRadius": "3px",
                    "backgroundColor": color,
                    "marginRight": "4px",
                    "verticalAlign": "middle"
                }),
                html.Span(exam_name, style={
                    "fontSize": "12px",
                    "marginRight": "16px",
                    "color": "var(--color-text-secondary)"
                })
            ])
        )
    legend = html.Div(legend_items, style={"marginBottom": "12px"})

    # build week days
    day_cols = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_rows = schedule[schedule["date"] == day]

        header = html.Div([
            html.Div(day.strftime("%a"), style={"fontSize": "12px", "color": "var(--color-text-secondary)"}),
            html.Div(day.strftime("%d %b"), style={"fontSize": "14px", "fontWeight": "500"})
        ], style={"marginBottom": "8px"})

        sessions = []
        if not day_rows.empty:
            for _, row in day_rows.iterrows():
                color = color_map.get(row["subject"], "hsl(0, 0%, 60%)")
                # strip exam prefix for display
                display_name = row["subject"]
                label = f"{display_name} {row['hours']}hrs"
                if spaced and row.get("type") == "review":
                    label += " (rev)"
                sessions.append(
                    html.Div(label, style={
                        "backgroundColor": color,
                        "color": "white",
                        "borderRadius": "4px",
                        "padding": "3px 6px",
                        "fontSize": "12px",
                        "marginBottom": "4px",
                        "whiteSpace": "nowrap",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis"
                    })
                )
        else:
            sessions.append(html.Div("—", style={
                "color": "var(--color-text-tertiary)",
                "fontSize": "12px"
            }))

        day_cols.append(
            html.Div([header] + sessions, style={
                "flex": "1",
                "minWidth": "0",
                "borderRight": "0.5px solid var(--color-border-tertiary)",
                "padding": "8px",
                "backgroundColor": "var(--color-background-primary)" if not day_rows.empty else "var(--color-background-secondary)"
            })
        )

    nav = html.Div([
        dbc.Button("← Prev", id="prev-week-button", color="secondary", size="sm"),
        html.Span(
            f"Week of {week_start.strftime('%b %d')} — {week_end.strftime('%b %d, %Y')}",
            style={"margin": "0 16px", "fontWeight": "500"}
        ),
        dbc.Button("Next →", id="next-week-button", color="secondary", size="sm"),
    ], style={"display": "flex", "alignItems": "center", "marginBottom": "12px"})

    calendar = html.Div(day_cols, style={
        "display": "flex",
        "border": "0.5px solid var(--color-border-tertiary)",
        "borderRadius": "8px",
        "overflow": "hidden"
    })

    return html.Div([nav, legend, calendar])


def build_tips(schedule, exam_dates, start, default_hours):
    """Build study tips from schedule DataFrame."""
    tips = generate_tips(schedule, exam_dates, start_date=start, default_hours=default_hours or 7)
    tip_items = []
    for tip in tips:
        tip_items.append(dbc.Alert(tip, color="info", className="mb-2"))
    return tip_items


def build_commitment_list():
    """Build commitment list with delete buttons."""
    items = []
    for i, c in enumerate(commitment_names):
        items.append(
            dbc.ListGroupItem([
                html.Span(f"🗓 {c['date']} — {c['hours']}hrs — {c['name']}"),
                dbc.Button("🗑️",
                    id={"type": "delete-commitment", "index": i},
                    color="danger",
                    size="sm",
                    className="float-end"
                )
            ])
        )
    return dbc.ListGroup(items) if items else html.P("No commitments added.")

# Callback — add exam
@app.callback(
    Output("exam-table", "children"),
    Input("add-exam-button", "n_clicks"),
    State("exam-name", "value"),
    State("exam-date", "date"),
    State("exam-hours", "value"),
    State("exam-topics", "value"),
    prevent_initial_call=True
)
def add_exam(n_clicks, name, exam_date, hours, topics):
    if not name or not exam_date or not hours:
        return dbc.Alert("Please fill in all required fields!", color="danger")

    topic_list = []
    if topics:
        for t in topics.split(","):
            stripped = t.strip()
            if stripped:
                topic_list.append(stripped)

    # check for duplicate topics before adding
    duplicate_warnings = []
    for existing_exam in exams:
        for topic in topic_list:
            if topic in existing_exam["topics"]:
                duplicate_warnings.append(
                    f"Topic '{topic}' already exists in '{existing_exam['name']}'. Please rename."
                )
    # check for duplicate exam names
    for existing_exam in exams:
        if existing_exam["name"] == name:
            return dbc.Alert(
                f"Exam '{name}' already exists. Please use a different name.",
                color="danger"
            )
    if duplicate_warnings:
        return dbc.Alert(" ".join(duplicate_warnings), color="danger")

    exams.append({
        "name": name,
        "date": exam_date,
        "hours": hours,
        "topics": topic_list
    })

    rows = []
    for i, e in enumerate(exams):
        rows.append(html.Tr([
            html.Td(e["name"]),
            html.Td(e["date"]),
            html.Td(f"{e['hours']}hrs"),
            html.Td(", ".join(e["topics"]) if e["topics"] else "—"),
            html.Td(dbc.Button("🗑️",
            id={"type": "delete-exam", "index": i},
            color="danger",
            size="sm"
            ))
        ]))

    table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("Exam"), html.Th("Date"),
            html.Th("Hours"), html.Th("Topics")
        ])),
        html.Tbody(rows)
    ], bordered=True, hover=True, striped=True, size="sm")

    return table

@app.callback(
    Output("exam-table", "children", allow_duplicate=True),
    Input({"type": "delete-exam", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def delete_exam(n_clicks_list):
    if not any(n_clicks_list):
        return dash.no_update

    triggered_index = ctx.triggered_id["index"]
    exams.pop(triggered_index)

    rows = []
    for i, e in enumerate(exams):
        rows.append(html.Tr([
            html.Td(e["name"]),
            html.Td(e["date"]),
            html.Td(f"{e['hours']}hrs"),
            html.Td(", ".join(e["topics"]) if e["topics"] else "—"),
            html.Td(dbc.Button("🗑️",
                id={"type": "delete-exam", "index": i},
                color="danger",
                size="sm"
            ))
        ]))

    table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("Exam"), html.Th("Date"),
            html.Th("Hours"), html.Th("Topics"), html.Th("")
        ])),
        html.Tbody(rows)
    ], bordered=True, hover=True, striped=True, size="sm")

    return table if exams else html.P("No exams added.")

# Callback — save exams
@app.callback(
    Output("save-button", "children"),
    Output("save-status", "children"), 
    Input("save-button", "n_clicks"),
    prevent_initial_call=True
)
def save_exams(n_clicks):
    if not exams:
        return "💾 Save", ""
    df = pd.DataFrame(exams)
    df["topics"] = df["topics"].apply(lambda t: ", ".join(t) if isinstance(t, list) else "")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    df.to_excel(os.path.join(BASE_DIR, "my_studysmart.xlsx"), index=False)
    return "💾 Save", "✅ Saved!"

# Callback — load exams
@app.callback(
    Output("exam-table", "children", allow_duplicate=True),
    Output("load-button", "children"),
    Input("load-button", "n_clicks"),
    prevent_initial_call=True
)
def load_exams(n_clicks):
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        df = pd.read_excel(os.path.join(BASE_DIR, "my_studysmart.xlsx"))
        df["date"] = pd.to_datetime(df["date"]).dt.date

        for _, row in df.iterrows():
            topic_list = []
            if pd.notna(row["topics"]) and row["topics"]:
                for t in row["topics"].split(","):
                    topic_list.append(t.strip())

            exams.append({
                "name": row["name"],
                "date": str(row["date"]),
                "hours": row["hours"],
                "topics": topic_list
            })

        rows = []
        for i, e in enumerate(exams):
            rows.append(html.Tr([
                html.Td(e["name"]),
                html.Td(e["date"]),
                html.Td(f"{e['hours']}hrs"),
                html.Td(", ".join(e["topics"]) if e["topics"] else "—"),
                html.Td(dbc.Button("🗑️",
                id={"type": "delete-exam", "index": i},
                color="danger",
                size="sm"
                ))
             ])) 

        table = dbc.Table([
            html.Thead(html.Tr([
                html.Th("Exam"), html.Th("Date"),
                html.Th("Hours"), html.Th("Topics"), html.Th("")
            ])),
            html.Tbody(rows)
        ], bordered=True, hover=True, striped=True, size="sm")

        return table, "✅ Loaded!"

    except FileNotFoundError:
        return html.P("No saved file found!"), "📂 Load"


# Callback — add commitment
@app.callback(
    Output("commitment-list", "children"),
    Input("add-commitment-button", "n_clicks"),
    State("commitment-date", "date"),
    State("commitment-name", "value"),
    State("commitment-hours", "value"),
    prevent_initial_call=True
)
def add_commitment(n_clicks, commitment_date, name, hours):
    if not commitment_date or not name or not hours:
        return dbc.Alert("Please fill in all fields!", color="danger")

    commitment_date_obj = date.fromisoformat(commitment_date)
    if commitment_date_obj in commitments:
        commitments[commitment_date_obj] += hours
    else:
        commitments[commitment_date_obj] = hours

    commitment_names.append({
        "date": commitment_date_obj,
        "name": name,
        "hours": hours
    })

    return build_commitment_list()


# Callback — delete commitment
@app.callback(
    Output("commitment-list", "children", allow_duplicate=True),
    Input({"type": "delete-commitment", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def delete_commitment(n_clicks_list):
    if not any(n_clicks_list):
        return dash.no_update

    triggered_index = ctx.triggered_id["index"]
    commitment_names.pop(triggered_index)

    commitments.clear()
    for c in commitment_names:
        if c["date"] in commitments:
            commitments[c["date"]] += c["hours"]
        else:
            commitments[c["date"]] = c["hours"]

    return build_commitment_list()


# Callback — import from Google Calendar
@app.callback(
    Output("commitment-list", "children", allow_duplicate=True),
    Output("import-calendar-button", "children"),
    Input("import-calendar-button", "n_clicks"),
    State("start-date", "date"),
    prevent_initial_call=True
)
def import_from_google_calendar(n_clicks, start_date):

    try:
        from study_smart.google_calendar import import_commitments_from_google_calendar
    
        if not exams:
            return dbc.Alert("Please add exams first!", color="warning"), "📅 Import from Google Calendar"

        end_date = max(date.fromisoformat(e["date"]) for e in exams)
        start = date.fromisoformat(start_date)

        imported, event_names = import_commitments_from_google_calendar(start, end_date)

        for d, h in imported.items():
            if d in commitments:
                commitments[d] += h
            else:
                commitments[d] = h
            commitment_names.append({
                "date": d,
                "name": "Google Calendar",
                "hours": h
            })

        return build_commitment_list(), "✅ Imported!"

    except Exception as e:
        return dbc.Alert(f"Could not import: {str(e)}", color="danger"), "📅 Import from Google Calendar"
    
# Callback — export to Google Calendar
@app.callback(
    Output("export-calendar-status", "children"),
    Output("export-calendar-button", "children"),
    Input("export-calendar-button", "n_clicks"),
    State("schedule-store", "data"),
    prevent_initial_call=True
)
def export_to_google_calendar(n_clicks, stored_schedule):
    try:
        from study_smart.google_calendar import export_schedule_to_google_calendar

        if not stored_schedule:
            return dbc.Alert("Please generate a schedule first!", color="warning"), "📅 Export to Google Calendar"

        schedule = pd.DataFrame(stored_schedule)
        schedule["date"] = pd.to_datetime(schedule["date"]).dt.date

        count = export_schedule_to_google_calendar(schedule)
        return dbc.Alert(f"✅ {count} events added to Google Calendar!", color="success"), "📅 Export to Google Calendar"

    except Exception as e:
        return dbc.Alert(f"Could not export: {str(e)}", color="danger"), "📅 Export to Google Calendar"
    
# Callback — navigate weeks
@app.callback(
    Output("current-week-store", "data"),
    Input("prev-week-button", "n_clicks"),
    Input("next-week-button", "n_clicks"),
    State("current-week-store", "data"),
    prevent_initial_call=True
)
def update_week(prev, next, current_week):
    if ctx.triggered_id == "prev-week-button":
        return current_week - 1
    return current_week + 1


# Callback — update weekly view when week changes
@app.callback(
    Output("schedule-list", "children", allow_duplicate=True),
    Input("current-week-store", "data"),
    State("schedule-store", "data"),
    State("spaced-repetition-store", "data"),
    State("color-map-store", "data"),
    State("exam-colors-store", "data"),
    prevent_initial_call=True
)
def update_weekly_view(week_offset, stored_schedule, spaced, color_map, exam_colors):
    if not stored_schedule:
        return dash.no_update
    schedule = pd.DataFrame(stored_schedule)
    schedule["date"] = pd.to_datetime(schedule["date"]).dt.date
    return build_weekly_view(
        schedule,
        spaced or False,
        week_offset=week_offset or 0,
        color_map=color_map,
        exam_colors=exam_colors
    )


# Callback — generate schedule
@app.callback(
    Output("schedule-chart", "figure"),
    Output("schedule-list", "children"),
    Output("warnings-div", "children"),
    Output("tips-div", "children"),
    Output("schedule-store", "data"),
    Output("spaced-repetition-store", "data"),
    Output("start-date-store", "data"),
    Output("current-week-store", "data", allow_duplicate=True),
    Output("color-map-store", "data"),
    Output("exam-colors-store", "data"),
    Output("legend-div", "children"),
    Input("generate-button", "n_clicks"),
    State("spaced-repetition-toggle", "value"),
    State("default-hours", "value"),
    State("start-date", "date"),

    prevent_initial_call=True
)
def generate_schedule(n_clicks, spaced_repetition, default_hours, start_date):
    if not exams:
        return {}, dbc.Alert("Please add exams first!", color="warning"), None, None, None, None, None, 0, None, None, None

    exam_list = []
    for e in exams:
        exam_list.append({
            "name": e["name"],
            "date": date.fromisoformat(e["date"]),
            "hours": float(e["hours"]),
            "topics": e["topics"]
        })

    start = date.fromisoformat(start_date)
    spaced = "on" in spaced_repetition

    schedule, warnings = build_schedule(
        exam_list,
        start_date=start,
        commitments=commitments,
        spaced_repetition=spaced
    )
    if schedule.empty:
        return {}, dbc.Alert("No schedule generated!", color="warning"), None, None, None, None, None, 0, None, None, None

    warning_cards = []
    for w in warnings:
        warning_cards.append(dbc.Alert(w, color="warning"))

    # build color maps — one color per exam shared across all its topics
    color_map, exam_colors = get_subject_color_map(schedule, exam_list)

    # build legend
    legend_items = []
    for exam_name, color in exam_colors.items():
        legend_items.append(
            html.Span([
                html.Span(style={
                    "display": "inline-block",
                    "width": "14px",
                    "height": "14px",
                    "borderRadius": "3px",
                    "backgroundColor": color,
                    "marginRight": "6px",
                    "verticalAlign": "middle"
                }),
                html.Span(exam_name, style={"marginRight": "16px", "fontSize": "14px"})
            ])
        )
    legend = html.Div(legend_items, className="mb-3")

    fig = build_chart(schedule, spaced, color_map)

    weekly = build_weekly_view(
        schedule, spaced,
        color_map=color_map,
        exam_colors=exam_colors,
        week_offset=0
    ) 
    exam_dates = {}
    
    for e in exam_list:
        exam_dates[e["name"]] = e["date"]
    tip_items = build_tips(schedule, exam_dates, start, default_hours)

    return fig, weekly, warning_cards, tip_items, schedule.to_dict('records'), spaced_repetition, start_date, 0, color_map, exam_colors, legend


if __name__ == "__main__":
    app.run(debug=True)


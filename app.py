# app.py
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime, timedelta
import csv, os, io
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "workhours-secret"
app.config['REPORT_FOLDER'] = 'static/reports'
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

def compute_duration(start_str, end_str):
    fmt = "%H:%M"
    try:
        start = datetime.strptime(start_str, fmt)
        end = datetime.strptime(end_str, fmt)
        if end < start:
            end += timedelta(days=1)
        return end - start
    except Exception:
        return timedelta(0)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET" and request.args.get("reset") == "1":
        session.clear()
        return redirect(url_for("index"))

    if request.method == "POST":
        total_duration = timedelta()
        breakdown = []
        day_offset = session.get("day_offset", 0)

        try:
            day_count = int(request.form.get("day_count", 0))
        except ValueError:
            day_count = 0

        for i in range(day_count):
            m_arrive = request.form.get(f"m_arrive_{i}", "")
            m_depart = request.form.get(f"m_depart_{i}", "")
            a_arrive = request.form.get(f"a_arrive_{i}", "")
            a_depart = request.form.get(f"a_depart_{i}", "")

            day_total = timedelta()
            if m_arrive and m_depart:
                day_total += compute_duration(m_arrive, m_depart)
            if a_arrive and a_depart:
                day_total += compute_duration(a_arrive, a_depart)

            total_duration += day_total
            hours = int(day_total.total_seconds() // 3600)
            minutes = int((day_total.total_seconds() % 3600) // 60)

            breakdown.append({
                "Day": f"Day {i + 1 + day_offset}",
                "Morning Arrival": m_arrive,
                "Morning Departure": m_depart,
                "Afternoon Arrival": a_arrive,
                "Afternoon Departure": a_depart,
                "Hours": hours,
                "Minutes": minutes
            })

        total_hours = int(total_duration.total_seconds() // 3600)
        total_minutes = int((total_duration.total_seconds() % 3600) // 60)

        breakdown.append({
            "Day": "TOTAL",
            "Morning Arrival": "-",
            "Morning Departure": "-",
            "Afternoon Arrival": "-",
            "Afternoon Departure": "-",
            "Hours": total_hours,
            "Minutes": total_minutes
        })

        session["breakdown"] = session.get("breakdown", []) + breakdown[:-1]
        session["day_offset"] = day_offset + day_count
        session["total_hours"] = session.get("total_hours", 0) + total_hours
        session["total_minutes"] = session.get("total_minutes", 0) + total_minutes

        csv_path = os.path.join(app.config['REPORT_FOLDER'], 'work_hours_report.csv')
        with open(csv_path, 'w', newline='') as csvfile:
            fieldnames = ["Day", "Morning Arrival", "Morning Departure",
                          "Afternoon Arrival", "Afternoon Departure", "Hours", "Minutes"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in session["breakdown"]:
                writer.writerow(row)
            writer.writerow(breakdown[-1])

        return redirect(url_for("index"))

    breakdown = session.get("breakdown", [])
    total_hours = session.get("total_hours", 0)
    total_minutes = session.get("total_minutes", 0)
    csv_ready = bool(breakdown)

    if csv_ready:
        breakdown = breakdown + [{
            "Day": "TOTAL",
            "Morning Arrival": "-",
            "Morning Departure": "-",
            "Afternoon Arrival": "-",
            "Afternoon Departure": "-",
            "Hours": total_hours,
            "Minutes": total_minutes
        }]

    return render_template("index.html", hours=total_hours, minutes=total_minutes,
                           breakdown=breakdown, csv_ready=csv_ready)

@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit_entry(index):
    breakdown = session.get("breakdown", [])
    if index >= len(breakdown):
        return redirect(url_for("index"))

    if request.method == "POST":
        m_arrive = request.form.get("m_arrive")
        m_depart = request.form.get("m_depart")
        a_arrive = request.form.get("a_arrive")
        a_depart = request.form.get("a_depart")

        entry = breakdown[index]
        entry["Morning Arrival"] = m_arrive
        entry["Morning Departure"] = m_depart
        entry["Afternoon Arrival"] = a_arrive
        entry["Afternoon Departure"] = a_depart

        day_total = timedelta()
        if m_arrive and m_depart:
            day_total += compute_duration(m_arrive, m_depart)
        if a_arrive and a_depart:
            day_total += compute_duration(a_arrive, a_depart)

        entry["Hours"] = int(day_total.total_seconds() // 3600)
        entry["Minutes"] = int((day_total.total_seconds() % 3600) // 60)

        session["breakdown"] = breakdown

        total_duration = timedelta()
        for row in breakdown:
            duration = timedelta(hours=row["Hours"], minutes=row["Minutes"])
            total_duration += duration
        session["total_hours"] = int(total_duration.total_seconds() // 3600)
        session["total_minutes"] = int((total_duration.total_seconds() % 3600) // 60)

        return redirect(url_for("index"))

    return render_template("edit.html", entry=breakdown[index], index=index)

@app.route("/upload_csv", methods=["POST"])
def upload_csv():
    file = request.files.get("csv_file")
    if not file:
        return redirect(url_for("index"))

    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    csv_input = csv.DictReader(stream)

    breakdown = []
    total_duration = timedelta()

    for row in csv_input:
        if row["Day"] == "TOTAL":
            continue

        m_arrive = row.get("Morning Arrival", "")
        m_depart = row.get("Morning Departure", "")
        a_arrive = row.get("Afternoon Arrival", "")
        a_depart = row.get("Afternoon Departure", "")

        day_total = timedelta()
        if m_arrive and m_depart:
            day_total += compute_duration(m_arrive, m_depart)
        if a_arrive and a_depart:
            day_total += compute_duration(a_arrive, a_depart)

        total_duration += day_total
        hours = int(day_total.total_seconds() // 3600)
        minutes = int((day_total.total_seconds() % 3600) // 60)

        breakdown.append({
            "Day": row["Day"],
            "Morning Arrival": m_arrive,
            "Morning Departure": m_depart,
            "Afternoon Arrival": a_arrive,
            "Afternoon Departure": a_depart,
            "Hours": hours,
            "Minutes": minutes
        })

    session["breakdown"] = breakdown
    session["day_offset"] = len(breakdown)
    session["total_hours"] = int(total_duration.total_seconds() // 3600)
    session["total_minutes"] = int((total_duration.total_seconds() % 3600) // 60)

    return redirect(url_for("index"))

@app.route("/download_csv")
def download_csv():
    path = os.path.join(app.config['REPORT_FOLDER'], 'work_hours_report.csv')
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

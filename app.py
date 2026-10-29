from flask import Flask, render_template, request, make_response, redirect, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import os

app = Flask(__name__)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Shubham@123",
    database="smart_travel_planner"
)

@app.route("/test-db")
def test_db():
    cursor = db.cursor()
    cursor.execute("SELECT * FROM destinations")
    data = cursor.fetchall()
    cursor.close()

    return str(data)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/plan-trip")
def plan_trip():
    return render_template("plan_trip.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()

            if user and check_password_hash(user["password"], password):
                return redirect(url_for("home"))

            return "Invalid email or password!"

        finally:
            cursor.close()

    return render_template("login.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        hashed_password = generate_password_hash(password)

        cursor = db.cursor()

        try:
            query = """
                INSERT INTO users (name, email, password)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (name, email, hashed_password))
            db.commit()
            return "Registration successful!"

        except mysql.connector.Error as err:
            db.rollback()
            return f"Registration failed: {err}"

        finally:
            cursor.close()

    return render_template("register.html")


def get_smart_suggestions(destination, interest, day, budget_per_person):
    destination_lower = destination.lower()

    # Destination-specific suggestions
    destination_plans = {
        "tarkarli": [
            ("Explore Tarkarli Beach in the morning.",
             "Discover the local Konkan coastline.",
             "Enjoy the sunset and try local food."),
            ("Visit a nearby coastal attraction.",
             "Explore local markets and Konkan culture.",
             "Relax near the beach in the evening."),
            ("Enjoy an early beach walk.",
             "Explore nearby places at a comfortable pace.",
             "Capture sunset photographs.")
        ],
        "rajgad": [
            ("Start early for the Rajgad Fort trek.",
             "Explore permitted fort trails and viewpoints.",
             "Rest and enjoy the mountain scenery."),
            ("Explore the fort's historic areas.",
             "Visit accessible viewpoints and take photographs.",
             "Plan your return before it gets dark."),
            ("Enjoy a morning nature walk.",
             "Explore remaining accessible fort areas.",
             "Return safely and rest.")
        ],
        "raigad": [
            ("Start early to explore Raigad Fort.",
             "Discover the fort's historic landmarks.",
             "Enjoy the mountain views and return safely."),
            ("Explore accessible historic areas.",
             "Learn about the fort's history.",
             "Capture scenic photographs before returning.")
        ],
        "shivneri": [
            ("Explore Shivneri Fort early in the day.",
             "Discover accessible historic landmarks.",
             "Enjoy the surrounding hill scenery."),
            ("Explore remaining accessible fort areas.",
             "Learn about the history of Shivneri.",
             "Take photographs and plan a safe return.")
        ],
        "theur": [
            ("Visit Shri Chintamani Ganpati Temple.",
             "Explore the local area respectfully.",
             "Enjoy a peaceful evening."),
            ("Attend darshan according to temple timings.",
             "Explore nearby local attractions.",
             "Relax and plan the next day's visit.")
        ]
    }

    # Interest-based suggestions
    interest_plans = {
        "Trekking": [
            ("Start your trek early.", "Explore the trail safely.",
             "Rest and enjoy the scenery."),
            ("Explore another accessible trail.",
             "Visit a viewpoint.", "Return before dark.")
        ],
        "Beaches": [
            ("Enjoy a morning beach walk.",
             "Explore the nearby coastline.",
             "Watch the sunset from a safe location."),
            ("Visit another accessible beach.",
             "Explore local coastal culture.",
             "Relax and enjoy the evening.")
        ],
        "Temples": [
            ("Visit a local temple.",
             "Explore nearby places respectfully.",
             "Spend a peaceful evening."),
            ("Visit another nearby place of worship.",
             "Explore local culture.",
             "Check the next day's temple timings.")
        ],
        "Historical Places": [
            ("Explore a historical landmark.",
             "Learn about its history.",
             "Take photographs at permitted viewpoints."),
            ("Discover another accessible historic area.",
             "Explore local heritage.",
             "Plan your return safely.")
        ],
        "Nature": [
            ("Enjoy a morning nature walk.",
             "Explore nearby scenic locations.",
             "Relax and enjoy the sunset."),
            ("Visit an accessible nature spot.",
             "Take landscape photographs.",
             "Rest and prepare for tomorrow.")
        ],
        "Waterfalls": [
            ("Check local safety conditions before visiting.",
             "Visit only permitted areas.",
             "Return before dark and avoid slippery edges.")
        ],
        "Camping": [
            ("Visit an approved camping location.",
             "Enjoy permitted outdoor activities.",
             "Follow campsite safety rules.")
        ],
        "Photography": [
            ("Capture photographs in morning light.",
             "Explore scenic photography spots.",
             "Try sunset photography from a safe viewpoint.")
        ],
        "Local Food": [
            ("Try local breakfast options.",
             "Explore regional dishes.",
             "Discover a local market or food stall.")
        ],
        "General": [
            ("Explore the main local attraction.",
             "Discover nearby places.",
             "Relax and enjoy the evening.")
        ]
    }


    # Find matching destination
    matched_destination = next(
        (key for key in destination_plans if key in destination_lower),
        None
    )

    # Use selected interest first
    if interest != "General":
        plans = interest_plans.get(
            interest, interest_plans["General"]
        )
    elif matched_destination:
        plans = destination_plans[matched_destination]
    else:
        plans = interest_plans["General"]

    # Rotate plans across trip days
    morning, afternoon, evening = plans[(day - 1) % len(plans)]

    # Budget-aware guidance
    if budget_per_person < 500:
        budget_tip = "Keep spending low; check transport and food costs beforehand."
    elif budget_per_person < 1500:
        budget_tip = "Compare local transport and food prices to stay on budget."
    else:
        budget_tip = "Keep some money aside for unexpected travel expenses."

    return {
        "morning": morning,
        "afternoon": afternoon,
        "evening": evening,
        "budget_tip": budget_tip
    }

@app.route("/generate-trip", methods=["POST"])
def generate_trip():
    destination = request.form.get("destination", "").strip()
    days = request.form.get("days", type=int)
    budget = request.form.get("budget", type=float)
    people = request.form.get("people", type=int)
    interests = request.form.getlist("interests")
    if (
        not destination or not days or budget is None or not people
        or days < 1 or budget <= 0 or people < 1
    ):
        return "Please enter valid trip details.", 400

    activities = {
        "Trekking": [
            "Start early and explore the trekking route.",
            "Visit a viewpoint and enjoy the mountain scenery.",
            "Explore nearby trails and take photographs."
        ],
        "Beaches": [
            "Visit the beach and enjoy the morning sea view.",
            "Explore the coastline and nearby beaches.",
            "Enjoy the sunset and relax by the sea."
        ],
        "Temples": [
            "Visit the main temple and attend darshan.",
            "Explore nearby temples and local attractions.",
            "Spend a peaceful evening near the temple."
        ],
        "Historical Places": [
            "Explore the main fort or historical monument.",
            "Discover historical landmarks and viewpoints.",
            "Learn about local history and capture photos."
        ],
        "Nature": [
            "Explore scenic locations and enjoy nature.",
            "Visit nearby hills, gardens or nature trails.",
            "Enjoy the sunset and relax in nature."
        ],
        "Waterfalls": [
            "Visit a nearby waterfall if conditions are safe.",
            "Explore permitted nature trails nearby.",
            "Enjoy the scenery and take photographs."
        ],
        "Camping": [
            "Explore an approved camping location.",
            "Enjoy outdoor activities in daylight.",
            "Relax at the campsite and follow local safety rules."
        ],
        "Photography": [
            "Capture scenic views in the morning light.",
            "Photograph local attractions and landscapes.",
            "Find a viewpoint for sunset photography."
        ],
        "Local Food": [
            "Try breakfast at a local food spot.",
            "Explore regional dishes for lunch.",
            "Visit a local market or food stall."
        ],
        "General": [
            "Explore the destination and nearby area.",
            "Visit a local attraction and enjoy sightseeing.",
            "Relax and prepare for the next day."
        ]
    }

    selected_interests = [
        item for item in interests if item in activities
    ]

    if not selected_interests:
        selected_interests = ["General"]

    destination_lower = destination.lower()

    itinerary = []
    destination_lower = destination.lower()

    for day in range(1, days + 1):

        chosen_interest = selected_interests[
            (day - 1) % len(selected_interests)
        ]

        # Get smart suggestions for this day
        suggestions = get_smart_suggestions(
            destination,
            chosen_interest,
            day,
            budget / people
        )

        morning = suggestions["morning"]
        afternoon = suggestions["afternoon"]
        evening = suggestions["evening"]

        # Destination-specific description
        if "tarkarli" in destination_lower:
            place_name = "Tarkarli Beach and the Konkan coast"
        elif "rajgad" in destination_lower:
            place_name = "Rajgad Fort and its surroundings"
        elif "raigad" in destination_lower:
            place_name = "Raigad Fort and its surroundings"
        elif "shivneri" in destination_lower:
            place_name = "Shivneri Fort and its surroundings"
        elif "theur" in destination_lower:
            place_name = "Shri Chintamani Ganpati Temple, Theur"
        elif "konkan" in destination_lower:
            place_name = "Konkan coastline and local attractions"
        else:
            place_name = destination

        itinerary.append({
            "day": day,
            "activity": f"Explore {place_name}.",
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "budget_tip": suggestions["budget_tip"]
        })

    budget_per_person = budget / people

    return render_template(
        "trip_result.html",
        destination=destination,
        days=days,
        budget=budget,
        people=people,
        interests=selected_interests,
        interest=", ".join(selected_interests),
        itinerary=itinerary,
        budget_per_person=budget_per_person
    )


@app.route("/destinations")
def destinations():

    cursor = db.cursor()
    cursor.execute("SELECT * FROM destinations")

    data = cursor.fetchall()

    cursor.close()

    return render_template("destinations.html", destinations=data)

@app.route("/destination/<int:destination_id>")
def destination_details(destination_id):
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM destinations WHERE destination_id = %s",
        (destination_id,)
    )

    destination = cursor.fetchone()
    cursor.close()

    if destination is None:
        return "Destination not found", 404

    return render_template(
        "destination_details.html",
        destination=destination
    )



def draw_pdf_image(pdf, image_path, x, y, width, height):
    if not os.path.exists(image_path):
        return False

    img = ImageReader(image_path)
    img_width, img_height = img.getSize()

    scale = min(width / img_width, height / img_height)
    draw_width = img_width * scale
    draw_height = img_height * scale

    pdf.drawImage(
        img,
        x + (width - draw_width) / 2,
        y + (height - draw_height) / 2,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto"
    )
    return True



@app.route("/download-trip-pdf", methods=["POST"])
def download_trip_pdf():
    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    destination = request.form.get("destination", "My Trip")
    days = request.form.get("days", "1")
    budget = request.form.get("budget", "0")
    people = request.form.get("people", "1")
    interests = request.form.getlist("interests")

    # Cover page
    place = destination.lower()

    if "tarkarli" in place or "beach" in place:
        image_name = "Tarkarli.jpeg"
    elif "shivneri" in place:
        image_name = "shivneri.jpeg"
    elif "theur" in place or "temple" in place:
        image_name = "theur2.jpeg"
    elif "rajgad" in place or "raigad" in place:
        image_name = "raigad.jpeg"
    else:
        image_name = "kokan_banner.jpeg"

    image_path = os.path.join(
        app.root_path, "static", "images", image_name
    )

    draw_pdf_image(
        pdf, image_path,
        50, height - 390,
        width - 100, 280
    )

    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(
        width / 2, height - 430, "Smart Travel Planner"
    )

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(
        width / 2, height - 465, destination.title()
    )

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(
        width / 2, height - 495, f"Duration: {days} days"
    )

    pdf.drawCentredString(
        width / 2, height - 515,
        f"Budget: Rs. {budget} | People: {people}"
    )

    # Start trip details on the next page
    pdf.showPage()

    destination = request.form.get("destination", "My Trip")
    days = request.form.get("days", "1")
    budget = request.form.get("budget", "0")
    people = request.form.get("people", "1")
    interests = request.form.getlist("interests")
    import json

    itinerary_text = request.form.get("itinerary_text", "[]")

    try:
        itinerary = json.loads(itinerary_text)
    except (json.JSONDecodeError, TypeError):
        itinerary = []

    y = height - 60

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "Smart Travel Planner")
    y -= 35

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Your Trip Plan")
    y -= 30

    pdf.setFont("Helvetica", 11)

    details = [
        f"Destination: {destination}",
        f"Duration: {days} days",
        f"Total Budget: Rs. {budget}",
        f"Number of People: {people}",
        f"Interests: {', '.join(interests) if interests else 'General'}"
    ]

    for detail in details:
        pdf.drawString(50, y, detail[:100])
        y -= 22

    # Day-wise itinerary
    for item in itinerary:

        # Select a photo for this day's interest
        if interests:
            day_interest = interests[
                (item.get("day", 1) - 1) % len(interests)
            ]
        else:
            day_interest = "General"

        if day_interest == "Temples":
            image_name = "theur2.jpeg"
        elif day_interest == "Nature":
            image_name = "kokan_banner.jpeg"
        elif day_interest == "Beaches":
            image_name = "Tarkarli.jpeg"
        elif day_interest == "Trekking":
            image_name = "raigad.jpeg"
        else:
            image_name = "kokan_food.jpeg"

        image_path = os.path.join(
            app.root_path, "static", "images", image_name
        )


        if y < 150:
            pdf.showPage()
            y = height - 60

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, f"Day {item.get('day', '')}")

        draw_pdf_image(
            pdf, image_path,
            width - 150, y - 85,
            100, 65
        )

        y -= 25

        pdf.setFont("Helvetica", 10)

        sections = [
            ("Activity", item.get("activity", "")),
            ("Morning", item.get("morning", "")),
            ("Afternoon", item.get("afternoon", "")),
            ("Evening", item.get("evening", "")),
            ("Budget Tip", item.get("budget_tip", ""))
        ]

        for label, content in sections:
            text = f"{label}: {content}"

            while text:
                if y < 60:
                    pdf.showPage()
                    y = height - 60
                    pdf.setFont("Helvetica", 10)

                pdf.drawString(50, y, text[:95])
                text = text[95:]
                y -= 15

        y -= 15

    # Travel Planning Note
    if y < 80:
        pdf.showPage()
        y = height - 60

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Travel Planning Note")
    y -= 25

    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        50, y,
        "Please check travel timings, weather and local costs."
    )
    y -= 20
    pdf.drawString(50, y, "This PDF contains your trip details.")

    pdf.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        "attachment; filename=smart_trip_plan.pdf"
    )

    return response

if __name__ == "__main__":
    app.run(debug=True)

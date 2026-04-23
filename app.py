from flask import Flask, render_template, request
import requests
import wikipedia
import json

app = Flask(__name__)

# ════════════════════════════════════════════════
#  API KEYS
# ════════════════════════════════════════════════
WEATHER_API_KEY = "6ad32c43f36552ded2ba3493b5835ed0"
GEMINI_API_KEY  = "AIzaSyAejI2Kr2tBybYH5_W76GQFGAaoN644xLE"


# ════════════════════════════════════════════════
#  GEMINI HELPER — calls Gemini REST API directly
#  No package needed — works 100% guaranteed
# ════════════════════════════════════════════════
def ask_gemini(prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        body = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }
        res  = requests.post(url, headers=headers, json=body, timeout=30)
        data = res.json()

        # Extract text from response
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()

    except Exception as e:
        print("Gemini API Error:", e)
        print("Response:", res.text if 'res' in locals() else "No response")
        return None


# ════════════════════════════════════════════════
#  FUNCTION 1 - Wikipedia Description
# ════════════════════════════════════════════════
def get_place_description(place):
    try:
        wikipedia.set_lang("en")
        return wikipedia.summary(place, sentences=3)
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            return wikipedia.summary(e.options[0], sentences=3)
        except:
            return "No description available."
    except:
        return "No description available."


# ════════════════════════════════════════════════
#  FUNCTION 2 - Live Weather
# ════════════════════════════════════════════════
def get_weather(city):
    try:
        url  = f"https://api.openweathermap.org/data/2.5/weather?q={city.strip()}&appid={WEATHER_API_KEY}&units=metric"
        res  = requests.get(url, timeout=10)
        data = res.json()
        if data.get("cod") != 200:
            return None
        return {
            "temp"      : round(data["main"]["temp"], 1),
            "humidity"  : data["main"]["humidity"],
            "condition" : data["weather"][0]["description"].title(),
            "wind"      : data["wind"]["speed"]
        }
    except Exception as e:
        print("Weather Error:", e)
        return None


# ════════════════════════════════════════════════
#  FUNCTION 3 - Nearby Hotels (OpenStreetMap)
# ════════════════════════════════════════════════
def get_hotels(destination):
    try:
        url    = "https://nominatim.openstreetmap.org/search"
        params = {
            "q"             : f"hotels {destination}",
            "format"        : "json",
            "limit"         : 6,
            "addressdetails": 1
        }
        headers = {"User-Agent": "WandrTravelApp/1.0"}
        res     = requests.get(url, params=params, headers=headers, timeout=10)
        data    = res.json()
        hotels  = []
        for place in data:
            parts   = place.get("display_name", "").split(",")
            name    = parts[0].strip()
            address = ", ".join(parts[1:3]).strip() if len(parts) > 1 else "Address not available"
            hotels.append({"name": name, "address": address})
        return hotels if hotels else None
    except Exception as e:
        print("Hotels Error:", e)
        return None


# ════════════════════════════════════════════════
#  FUNCTION 4 - Booking Links
# ════════════════════════════════════════════════
def get_booking_links(source, destination):
    src       = source.replace(" ", "+")
    dest      = destination.replace(" ", "+")
    src_slug  = source.lower().replace(" ", "-")
    dest_slug = destination.lower().replace(" ", "-")
    return {
        "flight": f"https://www.makemytrip.com/flights/search?tripType=O&itinerary={src}-{dest}",
        "train" : "https://www.irctc.co.in/nget/train-search",
        "bus"   : f"https://www.redbus.in/bus-tickets/{src_slug}-to-{dest_slug}"
    }


# ════════════════════════════════════════════════
#  FUNCTION 5 - AI Itinerary
# ════════════════════════════════════════════════
def get_itinerary(destination, days, budget):
    try:
        prompt = f"""You are an expert travel planner.
Create a {days}-day travel itinerary for {destination} with a total budget of Rs.{budget}.

Return ONLY a valid JSON array. No extra text. No markdown. No explanation.
Each item must have exactly two keys:
- "title": short 3-5 word day theme
- "plan": 2-3 sentences of activities

Return exactly {days} items.

Example:
[
  {{"title": "Arrival and Explore", "plan": "Check into hotel. Visit the main market in evening. Try local street food for dinner."}},
  {{"title": "Culture and History", "plan": "Visit historical monuments in morning. Explore local museum in afternoon. Rest in evening."}}
]"""

        raw = ask_gemini(prompt)
        if not raw:
            return None

        # Clean markdown if present
        if "```" in raw:
            parts = raw.split("```")
            raw   = parts[1] if len(parts) > 1 else raw
            if raw.lower().startswith("json"):
                raw = raw[4:]

        return json.loads(raw.strip())

    except Exception as e:
        print("Itinerary Parse Error:", e)
        return None


# ════════════════════════════════════════════════
#  FUNCTION 6 - Travel Tips
# ════════════════════════════════════════════════
def get_travel_tips(destination):
    try:
        prompt = f"""Give exactly 5 practical travel tips for visiting {destination}.
Tips should cover safety, food, transport, weather, and culture.

Return ONLY a JSON array of 5 strings. No extra text. No markdown.

Example:
["Carry cash as many shops do not accept cards.",
 "Try local street food but ensure it is freshly made.",
 "Use public transport to save money.",
 "Carry a light jacket as evenings can be cool.",
 "Always bargain at local markets."]"""

        raw = ask_gemini(prompt)
        if not raw:
            return None

        if "```" in raw:
            parts = raw.split("```")
            raw   = parts[1] if len(parts) > 1 else raw
            if raw.lower().startswith("json"):
                raw = raw[4:]

        return json.loads(raw.strip())

    except Exception as e:
        print("Tips Parse Error:", e)
        return None


# ════════════════════════════════════════════════
#  MAIN ROUTE
# ════════════════════════════════════════════════
@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        source      = request.form.get("source", "").strip()
        destination = request.form.get("destination", "").strip()
        budget      = request.form.get("budget", "1000").strip()
        days        = request.form.get("days", "1").strip()

        budget_int  = int(budget) if budget.isdigit() else 1000
        days_int    = int(days)   if days.isdigit()   else 1
        per_day     = budget_int  // days_int

        print(f"\n🌍 Planning: {source} → {destination} | {days} days | Rs.{budget}\n")

        description   = get_place_description(destination)
        weather       = get_weather(destination)
        hotels        = get_hotels(destination)
        booking_links = get_booking_links(source, destination)
        itinerary     = get_itinerary(destination, days_int, budget_int)
        tips          = get_travel_tips(destination)
        map_link      = f"https://www.google.com/maps/dir/{source.replace(' ','+')}/{destination.replace(' ','+')}"

        print("✅ Description :", "OK" if description else "FAILED")
        print("✅ Weather      :", "OK" if weather     else "FAILED")
        print("✅ Hotels       :", "OK" if hotels      else "FAILED")
        print("✅ Itinerary    :", "OK" if itinerary   else "FAILED")
        print("✅ Tips         :", "OK" if tips        else "FAILED")

        return render_template(
            "index.html",
            source        = source,
            destination   = destination,
            budget        = budget,
            days          = days,
            per_day       = per_day,
            description   = description,
            weather       = weather,
            hotels        = hotels,
            booking_links = booking_links,
            itinerary     = itinerary,
            tips          = tips,
            map_link      = map_link
        )

    return render_template("index.html")


# ════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════
# NEW
if __name__ == "__main__":
    app.run(debug=False)
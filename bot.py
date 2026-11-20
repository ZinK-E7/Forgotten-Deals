
import re
import json
import time
import html
import urllib.parse
import urllib.request

STATE_FILE = "posted_deals.json"
PENDING_FILE = "pending_deals.json"

TAGS = {
    "Horror": 1667,
    "Survival": 1662,
    "FPS": 1663,
    "Indie": 492,
}

MIN_DISCOUNT = 35
MAX_PAGES = 3


def load_json(filename, default):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, indent=2)


def get_html(element, class_name):
    match = re.search(
        r'<[^>]*class="[^"]*' + class_name +
        r'[^"]*"[^>]*>(.*?)</[^>]+>',
        element,
        re.S
    )
    if not match:
        return ""

    return html.unescape(
        re.sub(r"<[^>]+>", "", match.group(1))
    ).strip()


def get_attribute(element, attribute):
    match = re.search(
        r'\b' + attribute + r'="([^"]*)"',
        element
    )
    return html.unescape(match.group(1)) if match else ""


def steam_search(tag_id):
    games = []

    for page in range(MAX_PAGES):
        params = {
            "query": "",
            "start": page * 100,
            "count": 100,
            "category1": 998,
            "specials": 1,
            "tags": tag_id,
            "cc": "gb",
            "l": "english",
            "json": 1,
        }

        url = (
            "https://store.steampowered.com/search/results/?"
            + urllib.parse.urlencode(params)
        )

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 ForgottenDeals/1.0",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )
        except Exception as error:
            print("Steam search error:", error)
            break

        results = data.get("results_html", "")

        print(
            "Steam response:",
            "success =", data.get("success"),
            "| total_count =", data.get("total_count"),
            "| keys =", list(data.keys())
        )

        if not results:
            print("WARNING: Steam returned no results_html!")
            print("Response preview:", str(data)[:600])
            break

        cards = re.findall(
            r'<a\b(?=[^>]*class="[^"]*search_result_row)[^>]*>.*?</a>',
            results,
            re.S
        )

        print(f"Steam page {page + 1}: {len(cards)} listings")

        for card in cards:
            app_id = get_attribute(card, "data-ds-appid")
            name = get_html(card, "title")
            discount_text = get_html(card, "search_discount")

            discount_match = re.search(r"(\d+)", discount_text)

            if not app_id or not name or not discount_match:
                continue

            discount = int(discount_match.group(1))

            if discount < MIN_DISCOUNT:
                continue

            app_id = app_id.split(",")[0]

            image_match = re.search(
                r'<img[^>]+(?:src|data-src)="([^"]+)"',
                card
            )

            image = (
                html.unescape(image_match.group(1))
                if image_match else ""
            )

            games.append({
                "id": app_id,
                "name": name,
                "discount": discount,
                "original": get_html(card, "discount_original_price"),
                "final": get_html(card, "discount_final_price"),
                "image": image,
                "url": f"https://store.steampowered.com/app/{app_id}/",
            })

        if len(cards) < 100:
            break

    return games


def main():
    posted = set(load_json(STATE_FILE, []))
    pending = load_json(PENDING_FILE, {})

    if not isinstance(pending, dict):
        pending = {}

    total_found = 0

    for category, tag_id in TAGS.items():
        print(f"\nSearching {category} deals...")

        games = steam_search(tag_id)

        print(f"{category}: {len(games)} qualifying games found")

        for game in games:
            app_id = game["id"]

            if app_id in posted:
                continue

            total_found += 1

            if app_id not in pending:
                pending[app_id] = game
                pending[app_id]["categories"] = []

            if category not in pending[app_id]["categories"]:
                pending[app_id]["categories"].append(category)

            if game["discount"] > pending[app_id]["discount"]:
                pending[app_id].update({
                    "discount": game["discount"],
                    "original": game["original"],
                    "final": game["final"],
                })

        time.sleep(2)

    save_json(PENDING_FILE, pending)

    print("\n----------------------------")
    print(f"New qualifying results: {total_found}")
    print(f"Deals waiting for Friday: {len(pending)}")
    print("----------------------------")


if __name__ == "__main__":
    main()

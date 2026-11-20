
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
MAX_ITEMS_PER_CATEGORY = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 ForgottenDeals/1.0",
    "Accept": "application/json"
}


def load_json(filename, default):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, indent=2)


def get_json(url):
    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def steam_search(tag_id):
    items = []

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

        try:
            data = get_json(url)

        except Exception as error:
            print("Steam search error:", error)
            break

        page_items = data.get("items", [])

        print(
            f"Steam page {page + 1}: "
            f"{len(page_items)} items returned"
        )

        if not page_items:
            print("No more Steam items.")
            break

        items.extend(page_items)

        if len(page_items) < 100:
            break

    return items[:MAX_ITEMS_PER_CATEGORY]


def get_app_id(item):
    logo = item.get("logo", "")

    match = re.search(
        r"/apps/(\d+)/",
        logo
    )

    return match.group(1) if match else ""


def get_game_details(app_id):
    url = (
        "https://store.steampowered.com/api/appdetails?"
        + urllib.parse.urlencode({
            "appids": app_id,
            "cc": "gb",
            "l": "english",
            "filters": "basic,price_overview"
        })
    )

    try:
        data = get_json(url)

        result = data.get(app_id, {})

        if not result.get("success"):
            print(f"No Steam details for app {app_id}")
            return None

        game = result.get("data", {})
        price = game.get("price_overview")

        if not price:
            return None

        discount = int(price.get("discount_percent", 0))

        if discount < MIN_DISCOUNT:
            return None

        return {
            "id": app_id,
            "name": game.get("name", "Unknown game"),
            "discount": discount,
            "original": price.get("initial_formatted", ""),
            "final": price.get("final_formatted", ""),
            "image": game.get("header_image", ""),
            "url": f"https://store.steampowered.com/app/{app_id}/",
        }

    except Exception as error:
        print(f"App details error for {app_id}: {error}")
        return None


def main():
    posted = set(load_json(STATE_FILE, []))
    pending = load_json(PENDING_FILE, {})

    if not isinstance(pending, dict):
        pending = {}

    cache = {}
    total_found = 0

    for category, tag_id in TAGS.items():
        print(f"\nSearching {category} deals...")

        items = steam_search(tag_id)

        print(f"{category}: checking {len(items)} games")

        category_found = 0

        for item in items:
            app_id = get_app_id(item)

            if not app_id:
                print("Skipping item without an app ID:", item.get("name"))
                continue

            if app_id in posted:
                continue

            if app_id not in cache:
                cache[app_id] = get_game_details(app_id)
                time.sleep(0.3)

            game = cache[app_id]

            if not game:
                continue

            category_found += 1

            if app_id not in pending:
                pending[app_id] = game.copy()
                pending[app_id]["categories"] = []

                total_found += 1

            if category not in pending[app_id]["categories"]:
                pending[app_id]["categories"].append(category)

            if game["discount"] > pending[app_id]["discount"]:
                pending[app_id].update({
                    "discount": game["discount"],
                    "original": game["original"],
                    "final": game["final"],
                    "image": game["image"],
                })

        print(
            f"{category}: {category_found} qualifying games found"
        )

        time.sleep(2)

    save_json(PENDING_FILE, pending)

    print("\n----------------------------")
    print(f"New qualifying results: {total_found}")
    print(f"Deals waiting for Friday: {len(pending)}")
    print("----------------------------")


if __name__ == "__main__":
    main()

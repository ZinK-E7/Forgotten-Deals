import os
import re
import json
import time
import html
import urllib.parse
import urllib.request

WEBHOOK = os.environ["DISCORD_WEBHOOK"]
STATE_FILE = "posted_deals.json"

# Steam community tag IDs
TAGS = {
    "Horror": 1667,
    "Survival": 1662,
    "FPS": 1663,
    "Indie": 492,
}

MIN_DISCOUNT = 35
MAX_PAGES = 3


def get_html(element, class_name):
    match = re.search(
        r'<[^>]*class="[^"]*' + class_name +
        r'[^"]*"[^>]*>(.*?)</[^>]+>',
        element,
        re.S
    )
    if not match:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()


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
            headers={"User-Agent": "ForgottenDeals/1.0"}
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            print("Steam search error:", error)
            break

        results = data.get("results_html", "")
        if not results:
            break

        cards = re.findall(
            r'<a\b(?=[^>]*class="[^"]*search_result_row)[^>]*>.*?</a>',
            results,
            re.S
        )

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

            original = get_html(card, "discount_original_price")
            final = get_html(card, "discount_final_price")

            image_match = re.search(
                r'<img[^>]+(?:src|data-src)="([^"]+)"',
                card
            )
            image = html.unescape(image_match.group(1)) if image_match else ""

            games.append({
                "id": app_id.split(",")[0],
                "name": name,
                "discount": discount,
                "original": original,
                "final": final,
                "image": image,
                "url": f"https://store.steampowered.com/app/{app_id.split(',')[0]}/",
            })

        if len(cards) < 100:
            break

    return games


def post_to_discord(game, categories):
    category_text = " • ".join(sorted(categories))

    embed = {
        "title": game["name"],
        "url": game["url"],
        "description": (
            f"🔥 **{game['discount']}% OFF**\n"
            f"~~{game['original']}~~  **{game['final']}**\n\n"
            f"**Genres:** {category_text}"
        ),
        "color": 0x39A852,
        "footer": {"text": "Forgotten Few | Forgotten Deals"},
    }

    if game["image"]:
        embed["thumbnail"] = {"url": game["image"]}

    payload = {"embeds": [embed]}

    request = urllib.request.Request(
        WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def main():
    try:
        with open(STATE_FILE, "r") as file:
            posted = set(json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        posted = set()

    found = {}

    for category, tag_id in TAGS.items():
        print(f"Searching {category} deals...")
        for game in steam_search(tag_id):
            app_id = game["id"]

            if app_id not in found:
                found[app_id] = {"game": game, "categories": set()}

            found[app_id]["categories"].add(category)

        time.sleep(2)

    new_deals = 0

    for app_id, item in found.items():
        if app_id in posted:
            continue

        try:
            post_to_discord(item["game"], item["categories"])
            posted.add(app_id)
            new_deals += 1
            print("Posted:", item["game"]["name"])
            time.sleep(1.5)

        except Exception as error:
            print("Discord posting error:", error)

    with open(STATE_FILE, "w") as file:
        json.dump(sorted(posted), file, indent=2)

    print(f"Finished! Posted {new_deals} new deals.")


if __name__ == "__main__":
    main()

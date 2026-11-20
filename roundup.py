
import os
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

WEBHOOK = os.environ["DISCORD_WEBHOOK"]

PENDING_FILE = "pending_deals.json"
STATE_FILE = "posted_deals.json"

MAX_DEALS = 20
MIN_DISCOUNT = 35

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


def get_current_game(app_id):
    url = (
        "https://store.steampowered.com/api/appdetails?"
        + urllib.parse.urlencode({
            "appids": app_id,
            "cc": "gb",
            "l": "english",
            "filters": "basic,price_overview"
        })
    )

    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    result = data.get(app_id, {})

    if not result.get("success"):
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


def post_roundup(games, first_batch):
    embeds = []

    for game in games:
        categories = " • ".join(
            sorted(game.get("categories", []))
        )

        embed = {
            "title": game["name"][:256],
            "url": game["url"],
            "description": (
                f"🔥 **{game['discount']}% OFF**\n"
                f"~~{game['original']}~~ "
                f"**{game['final']}**\n\n"
                f"**Genres:** {categories}"
            ),
            "color": 0x39A852,
            "footer": {
                "text": "Forgotten Few | Forgotten Deals"
            }
        }

        if game.get("image"):
            embed["thumbnail"] = {
                "url": game["image"]
            }

        embeds.append(embed)

    payload = {
        "content": (
            "🔥 **FORGOTTEN DEALS — FRIDAY ROUNDUP**\n"
            "This week's top 20 Steam bargains are here!"
            if first_batch else
            "🔥 **FORGOTTEN DEALS — MORE BARGAINS**"
        ),
        "embeds": embeds,
        "allowed_mentions": {"parse": []}
    }

    request = urllib.request.Request(
        WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def main():
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    now = datetime.now(ZoneInfo("Europe/London"))

    if event != "workflow_dispatch":
        if now.weekday() != 4 or now.hour != 12:
            print("Not Friday at UK lunchtime. Skipping.")
            return

    pending = load_json(PENDING_FILE, {})
    posted = set(load_json(STATE_FILE, []))

    if not pending:
        print("No waiting deals.")
        return

    print("Checking current Steam prices...")

    valid_games = []
    stale_ids = []

    for app_id, old_game in pending.items():
        if app_id in posted:
            stale_ids.append(app_id)
            continue

        try:
            game = get_current_game(app_id)

            if not game:
                print(f"Expired or no longer discounted: {old_game.get('name')}")
                stale_ids.append(app_id)
                continue

            game["categories"] = old_game.get("categories", [])
            valid_games.append(game)

            print(
                f"Verified: {game['name']} - "
                f"{game['discount']}% OFF"
            )

        except Exception as error:
            print(f"Could not check {old_game.get('name')}: {error}")

        time.sleep(0.3)

    for app_id in stale_ids:
        pending.pop(app_id, None)

    save_json(PENDING_FILE, pending)

    valid_games.sort(
        key=lambda game: game.get("discount", 0),
        reverse=True
    )

    games = valid_games[:MAX_DEALS]

    if not games:
        print("No verified deals ready to publish.")
        return

    print(f"Preparing top {len(games)} deals.")

    for start in range(0, len(games), 10):
        batch = games[start:start + 10]

        post_roundup(
            batch,
            first_batch=(start == 0)
        )

        for game in batch:
            app_id = game["id"]
            posted.add(app_id)
            pending.pop(app_id, None)

        save_json(STATE_FILE, sorted(posted))
        save_json(PENDING_FILE, pending)

        print(f"Published {len(batch)} deals.")

    print("Forgotten Deals roundup completed!")


if __name__ == "__main__":
    main()

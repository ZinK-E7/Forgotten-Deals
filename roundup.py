
import os
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

WEBHOOK = os.environ["DISCORD_WEBHOOK"]

PENDING_FILE = "pending_deals.json"
STATE_FILE = "posted_deals.json"


def load_json(filename, default):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, indent=2)


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
                f"~~{game.get('original', '')}~~ "
                f"**{game.get('final', '')}**\n\n"
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
            "This week's Steam bargains are here!"
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
        print("No waiting deals for this Friday.")
        return

    games = [
        game for app_id, game in pending.items()
        if app_id not in posted
    ]

    games.sort(
        key=lambda game: game.get("discount", 0),
        reverse=True
    )

    if not games:
        print("No new deals to publish.")
        return

    print(f"Preparing Friday roundup: {len(games)} games")

    # Discord supports a maximum of 10 embeds per message.
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

        # Save after each successful Discord message.
        save_json(STATE_FILE, sorted(posted))
        save_json(PENDING_FILE, pending)

        print(f"Published {len(batch)} deals")

    print("Friday roundup completed successfully!")


if __name__ == "__main__":
    main()

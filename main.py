import mlbstatsapi
import asyncio
import aiohttp

START_GAME = 662200
NUM_GAMES = 250

def calc_boring(game):
    boring_factor = 0

    # Game duration
    duration = game["gameData"]["gameInfo"]["gameDurationMinutes"]
    if duration is not None:
        boring_factor += duration * 0.5
    else:
        boring_factor += game["gameData"]["gameInfo"].get("delayDurationMinutes", 0) * 1.0

    # Attendance
    boring_factor += game["gameData"]["gameInfo"].get("attendance", 0) * 0.003

    # Reviews
    boring_factor += game["gameData"]["review"]["home"]["used"] * 3
    boring_factor += game["gameData"]["review"]["away"]["used"] * 3

    # Team records
    home_record = game["gameData"]["teams"]["home"]["record"]
    away_record = game["gameData"]["teams"]["away"]["record"]
    boring_factor += float(home_record["winningPercentage"]) * -60
    boring_factor += float(away_record["winningPercentage"]) * -40
    boring_factor += home_record["losses"] * 0.6
    boring_factor += away_record["losses"] * 0.4

    # Mound visits
    boring_factor += game["gameData"]["moundVisits"]["home"]["used"] * 3
    boring_factor += game["gameData"]["moundVisits"]["away"]["used"] * 3

    # NEW: Total runs (fewer runs = more boring)
    total_runs = (
        game["liveData"]["linescore"]["teams"]["home"]["runs"] +
        game["liveData"]["linescore"]["teams"]["away"]["runs"]
    )
    boring_factor += total_runs * -2  # More runs = less boring

    # NEW: Total hits (more hits = less boring)
    total_hits = (
        game["liveData"]["linescore"]["teams"]["home"]["hits"] +
        game["liveData"]["linescore"]["teams"]["away"]["hits"]
    )
    boring_factor += total_hits * -0.5

    # NEW: Total left on base (lots of missed chances = more boring)
    total_lob = (
        game["liveData"]["linescore"]["teams"]["home"].get("leftOnBase", 0) +
        game["liveData"]["linescore"]["teams"]["away"].get("leftOnBase", 0)
    )
    boring_factor += total_lob * 0.4

    # NEW: Extra innings (more = potentially more boring if it's a low-scoring slog)
    num_innings = len(game["liveData"]["linescore"]["innings"])
    if num_innings > 9:
        boring_factor += (num_innings - 9) * 2

    # NEW: Dead-air innings (no runs, no hits, no errors = nothing happened)
    dead_air_innings = 0
    for inning in game["liveData"]["linescore"]["innings"]:
        for side in ["home", "away"]:
            stats = inning.get(side, {})
            if stats.get("runs", 0) == 0 and stats.get("hits", 0) == 0 and stats.get("errors", 0) == 0:
                dead_air_innings += 1
    boring_factor += dead_air_innings * 1.5

    return int(boring_factor)

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, "https://statsapi.mlb.com/api/v1.1/game/" + str(i) + "/feed/live") for i in range(START_GAME, START_GAME+NUM_GAMES)]
        results = await asyncio.gather(*tasks)

        boring = {"game_id": 0, "score": 0}
        for i, result in enumerate(results):
            score = calc_boring(result)
            if boring["score"] < score:
                boring["score"] = score
                boring["id"] = i+START_GAME

        print(boring)


asyncio.run(main())
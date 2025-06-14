import mlbstatsapi
import asyncio
import aiohttp

START_GAME = 745234
NUM_GAMES = 1050

def calc_boring(game):
    try:
        boring_factor = 0

        # Game duration and delays
        duration = game["gameData"]["gameInfo"].get("gameDurationMinutes")
        if duration is not None:
            boring_factor += duration * 0.05
        else:
            boring_factor += game["gameData"]["gameInfo"].get("delayDurationMinutes", 0) * 0.1

        # Attendance
        boring_factor += game["gameData"]["gameInfo"].get("attendance", 0) * 0.0003

        # Reviews
        boring_factor += game["gameData"]["review"]["home"].get("used", 0) * 1
        boring_factor += game["gameData"]["review"]["away"].get("used", 0) * 1

        # Team records
        home_record = game["gameData"]["teams"]["home"]["record"]
        away_record = game["gameData"]["teams"]["away"]["record"]
        boring_factor += float(home_record.get("winningPercentage", 0)) * -0.6
        boring_factor += float(away_record.get("winningPercentage", 0)) * -0.4
        boring_factor += home_record.get("losses", 0) * 0.06
        boring_factor += away_record.get("losses", 0) * 0.04

        # Mound visits
        boring_factor += game["gameData"]["moundVisits"]["home"].get("used", 0) * 0.3
        boring_factor += game["gameData"]["moundVisits"]["away"].get("used", 0) * 0.3

        # Extra innings
        innings = game["liveData"]["linescore"].get("innings", [])
        num_innings = len(innings)
        if num_innings > 9:
            boring_factor += (num_innings - 9) * 2

        # Dead-air innings
        dead_air_innings = 0
        for inning in innings:
            for side in ["home", "away"]:
                stats = inning.get(side, {})
                if (
                    stats.get("runs", 0) == 0 and
                    stats.get("hits", 0) == 0 and
                    stats.get("errors", 0) == 0
                ):
                    dead_air_innings += 1
        boring_factor += dead_air_innings * 1.5

        # Lead changes
        score_home = 0
        score_away = 0
        last_leader = None
        lead_changes = 0

        for inning in innings:
            score_home += inning.get("home", {}).get("runs", 0)
            score_away += inning.get("away", {}).get("runs", 0)
            current_leader = (
                "home" if score_home > score_away else
                "away" if score_away > score_home else
                "tie"
            )
            if last_leader is not None and current_leader != last_leader and current_leader != "tie":
                lead_changes += 1
            last_leader = current_leader

        boring_factor += lead_changes * -3  # More lead changes = less boring

        # Weighted runs/hits by inning
        weighted_runs = 0
        weighted_hits = 0
        score_home_total = game["liveData"]["linescore"]["teams"]["home"]["runs"]
        score_away_total = game["liveData"]["linescore"]["teams"]["away"]["runs"]

        for i, inning in enumerate(innings, start=1):
            inning_weight = 1.0
            score_diff = abs(score_home_total - score_away_total)

            if i >= 7:  # late innings
                inning_weight = 1.5 if score_diff <= 2 else 0.5
            elif 4 <= i <= 6:  # middle innings
                inning_weight = 1.2

            for side in ["home", "away"]:
                stats = inning.get(side, {})
                weighted_runs += stats.get("runs", 0) * inning_weight
                weighted_hits += stats.get("hits", 0) * inning_weight

        boring_factor += weighted_runs * -2
        boring_factor += weighted_hits * -0.5

        # Left on base
        total_lob = (
            game["liveData"]["linescore"]["teams"]["home"].get("leftOnBase", 0) +
            game["liveData"]["linescore"]["teams"]["away"].get("leftOnBase", 0)
        )
        boring_factor += total_lob * 0.4

        # Pitching changes: count number of pitchers used
        def count_pitchers(team_data):
            return sum(
                1 for player in team_data.get("players", {}).values()
                if "pitching" in player.get("stats", {})
            )

        home_pitchers = count_pitchers(game["liveData"]["boxscore"]["teams"]["home"])
        away_pitchers = count_pitchers(game["liveData"]["boxscore"]["teams"]["away"])
        total_pitchers = home_pitchers + away_pitchers
        boring_factor += total_pitchers * 0.5  # each new pitcher slightly increases boring

        return int(boring_factor)

    except (KeyError, TypeError, ValueError):
        return None

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
            if score is None:
                print("Could not get score for game " + str(i + START_GAME))
                continue
            if boring["score"] < score:
                boring["score"] = score
                boring["id"] = i+START_GAME

        print(boring)


asyncio.run(main())
import mlbstatsapi
import asyncio
import aiohttp
import csv

START_GAME = 745234
NUM_GAMES = 100

def calc_boring_details(game):
    try:
        # Special flags
        flags = game["gameData"].get("flags", {})
        if flags.get("noHitter") or flags.get("perfectGame"):
            return {
                "boringScore": 0,
                "reason": "Special game (no-hitter or perfect game)"
            }

        boring_factor = 0
        game_info = game["gameData"]["gameInfo"]
        linescore = game["liveData"]["linescore"]
        score_home = linescore["teams"]["home"]["runs"]
        score_away = linescore["teams"]["away"]["runs"]
        total_runs = score_home + score_away
        total_hits = linescore["teams"]["home"]["hits"] + linescore["teams"]["away"]["hits"]
        score_diff = abs(score_home - score_away)

        # Game duration
        innings = game["liveData"]["linescore"].get("innings", [])
        num_innings = len(innings)

        duration = game_info.get("gameDurationMinutes")
        delay = game_info.get("delayDurationMinutes", 0)
        if num_innings <= 9:
            if duration is not None:
                duration_score = round((duration - 150) / 3)
                duration_score += round(delay / 1.5)
            else:
                duration_score = round(delay / 3)
            boring_factor += duration_score
        else:
            duration_score = 0

        # Attendance
        attendance = game_info.get("attendance", 0)
        attendance_score = round((25000 - attendance) / 2500)
        boring_factor += attendance_score

        # Reviews
        reviews_home = game["gameData"]["review"]["home"].get("used", 0)
        reviews_away = game["gameData"]["review"]["away"].get("used", 0)
        boring_factor += (reviews_home + reviews_away)

        # Mound visits
        mound_home = game["gameData"]["moundVisits"]["home"].get("used", 0)
        mound_away = game["gameData"]["moundVisits"]["away"].get("used", 0)
        boring_factor += (mound_home + mound_away) * 0.3

        # Winning % penalty
        home_record = game["gameData"]["teams"]["home"]["record"]
        away_record = game["gameData"]["teams"]["away"]["record"]
        win_pct_home = float(home_record.get("winningPercentage", 0))
        win_pct_away = float(away_record.get("winningPercentage", 0))
        losses_home = home_record.get("losses", 0)
        losses_away = away_record.get("losses", 0)

        # Approximate season progress
        total_games = lambda rec: rec.get("wins", 0) + rec.get("losses", 0)
        season_progress = min(
            max(total_games(home_record), total_games(away_record)) / 162, 1
        )

        # Boring if BOTH teams are bad
        bad_team_penalty = (1 - win_pct_home) * (1 - win_pct_away) * season_progress * 20
        boring_factor += bad_team_penalty

        # Other record-based contributions
        boring_factor += losses_home * 0.06 + losses_away * 0.04

        # Extra innings
        if len(innings) > 9:
            boring_factor += (len(innings) - 9) * 2

        # Dead-air innings
        dead_air_innings = 0
        for inning in innings:
            for side in ["home", "away"]:
                stats = inning.get(side, {})
                if stats.get("runs", 0) == 0 and stats.get("hits", 0) == 0 and stats.get("errors", 0) == 0:
                    dead_air_innings += 1
        boring_factor += dead_air_innings * 1.5

        # Lead changes
        running_home = running_away = 0
        last_leader = None
        lead_changes = 0
        for inning in innings:
            running_home += inning.get("home", {}).get("runs", 0)
            running_away += inning.get("away", {}).get("runs", 0)
            leader = (
                "home" if running_home > running_away else
                "away" if running_away > running_home else "tie"
            )
            if last_leader and leader != last_leader and leader != "tie":
                lead_changes += 1
            last_leader = leader
        boring_factor += lead_changes * -3

        # Last run excitement
        last_run_inning = None
        late_runs = 0
        weighted_hits = 0
        for i, inning in enumerate(innings, start=1):
            if inning.get("home", {}).get("runs", 0) > 0 or inning.get("away", {}).get("runs", 0) > 0:
                last_run_inning = i
            weight = 1.5 if i >= 7 and score_diff <= 2 else 0.5 if i >= 7 else 1.0
            for side in ["home", "away"]:
                if i >= 7:
                    late_runs += inning.get(side, {}).get("runs", 0)
                weighted_hits += inning.get(side, {}).get("hits", 0) * weight

        if last_run_inning and last_run_inning <= 3:
            boring_factor += 4
        if late_runs > 0 and score_diff <= 2:
            boring_factor += -5
        boring_factor += weighted_hits * -0.5

        # Left on base
        lob = linescore["teams"]["home"].get("leftOnBase", 0) + linescore["teams"]["away"].get("leftOnBase", 0)
        boring_factor += lob * 0.4

        # Total runs
        if 3 <= total_runs <= 5:
            boring_factor += 4
        elif total_runs > 10:
            boring_factor += -3

        # Pitching changes
        pitchers_home = len(game["liveData"]["boxscore"]["teams"]["home"].get("pitchers", []))
        pitchers_away = len(game["liveData"]["boxscore"]["teams"]["away"].get("pitchers", []))
        total_pitchers = pitchers_home + pitchers_away
        boring_factor += total_pitchers * 0.5

        return {
            "boringScore": int(boring_factor),
            "gamePk": game.get("gamePk"),
            "scoreHome": score_home,
            "scoreAway": score_away,
            "scoreDiff": score_diff,
            "totalRuns": total_runs,
            "totalHits": total_hits,
            "lateRuns": late_runs,
            "lastRunInning": last_run_inning or "None",
            "leadChanges": lead_changes,
            "deadAirInnings": dead_air_innings,
            "totalLOB": lob,
            "pitchersUsed": total_pitchers,
            "moundVisits": mound_home + mound_away,
            "reviews": reviews_home + reviews_away,
            "durationScore": round(duration_score, 2),
            "numInnings": num_innings,
            "attendanceScore": round(attendance_score, 2),
            "badTeamsPenalty": round(bad_team_penalty, 2),
            "winPctHome": round(win_pct_home, 3),
            "winPctAway": round(win_pct_away, 3),
            "seasonProgress": round(season_progress, 3),
            "reason": ""
        }

    except (KeyError, TypeError, ValueError):
        return None

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, "https://statsapi.mlb.com/api/v1.1/game/" + str(i) + "/feed/live") for i in range(START_GAME, START_GAME+NUM_GAMES)]
        data = await asyncio.gather(*tasks)

        boring = {"game_id": 0, "score": 10000}
        results = []
        for i, element in enumerate(data):
            score = calc_boring_details(element)
            if score is None:
                print("Could not get score for game " + str(i + START_GAME))
                continue
            if score:
                results.append(score)
        with open("boring_games_report.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

        print(boring)


asyncio.run(main())
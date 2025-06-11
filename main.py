import mlbstatsapi

def calc_boring(game):
    boring_factor = 0
    boring_factor += game.gameinfo.gamedurationminutes * 0.5
    if game.gameinfo.gamedurationminutes is None:
        boring_factor += game.gameinfo.delaydurationminutes * 1
    boring_factor += game.gameinfo.attendance * 0.003
    boring_factor += game.review.home.used * 3
    boring_factor += game.review.away.used * 3
    boring_factor += float(game.teams.home.record.winningpercentage) * -60
    boring_factor += float(game.teams.away.record.winningpercentage) * -40
    boring_factor += game.teams.home.record.losses * 0.6
    boring_factor += game.teams.away.record.losses * 0.4
    boring_factor += game.moundvisits.home.get("used") * 3
    boring_factor += game.moundvisits.away.get("used") * 3
    return boring_factor

def main():
    mlb = mlbstatsapi.Mlb()
    max_boring = {"id": 0, "score": 0}
    for i in range(662200, 662300):
        game = mlb.get_game(i).gamedata
        boring_factor = calc_boring(game)
        if boring_factor > max_boring["score"]:
            max_boring["score"] = boring_factor
            max_boring["id"] = i
    print(max_boring)

if __name__ == "__main__":
    main()
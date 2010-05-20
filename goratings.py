#!/usr/bin/env python
#
# Copyright (c) 2010 Benjamin Oris Jr. All rights reserved.

"""Go ratings program.

Computes ELO-based ratings for go players.
"""

import gdata.spreadsheet.text_db
import math
import random
import optparse
import sys


class Database:
    """Provides interface to a database.

    The database being used now is a Google spreadsheet.
    """

    def __init__(self, user=None, pasw=None):
        self.client = gdata.spreadsheet.text_db.DatabaseClient(username=user,
                    password=pasw)
        self.db = self.client.GetDatabases(name='Sid')[0]
        self.players_table = self.db.GetTables(name='players')[0]
        self.games_table = self.db.GetTables(name='games')[0]

    def SyncRatings(self):
        """Synchronizes the Rating in the Players worksheet
        and the Base Rating in the Games worksheet.
        """
        for player_row in self.players_table.FindRecords('id != ""'):
            rating = float(player_row.content['rating'])
            player_row.content['rating'] = str(round(rating))
            query = 'player == ' + player_row.content['id']
            game_row = self.games_table.FindRecords(query)[0]
            game_row.content['baserating'] = str(round(rating))
            player_row.Push()
            game_row.Push()

    def AddPlayer(self):
        verify = 'n'
        while verify != 'y':
            lastname = raw_input('Last name: ')
            firstnames = raw_input('First name(s): ')
            rating = int(raw_input('Rating: '))
            verify = raw_input('Are the entries correct?(y/n) ')
        while True:
            new_id = str(random.randint(100, 999))
            if not self.players_table.FindRecords('id == ' + str(new_id)):
                break
        self.players_table.AddRecord({'id': new_id, 'lastname': lastname,
                                         'firstnames': firstnames, 'rating':
                                            str(rating), 'grade':
                                            self.grades[rating]})
        self.games_table.AddRecord({'player': new_id, 'baserating':
                                          str(rating)})

    def GetRating(self, pid):
        """Get base rating from games worksheet.
        """
        player = self.games_table.FindRecords(
                                             'player == ' + str(pid))[0]
        return player.content['baserating']

    def GetGames(self):
        """Get game results from games worksheet.

        Returns a list of tuples.
        """
        results = []
        tourney_classes = {'a': 1.0, 'b': 0.75, 'c': 0.5}
        games = self.games_table.FindRecords('games != ""')
        if len(games) == 0:
            raise RuntimeError('no games in database')
        for row in games:
            pid1 = row.content['player']
            rating1 = self.GetRating(pid1)
            for g in row.content['games'].split(','):
                game = g.split('+')
                pid2 = game[0].strip()
                rating2 = self.GetRating(pid2)
                h = game[1][0]
                t = tourney_classes[game[1][1].strip()]
                results.append((pid1, rating1, pid2, rating2, h, t))
        return results

    def UpdateRating(self, pid, increment, dry_run):
        # Mapping of ratings to kyu and dan grades.
        self.grades = dict([(x, str(20 - (x - 100) / 100) + 'k')
            for x in range(100, 2100, 100)] + [(x, str((x - 2000) / 100) + 'd')
            for x in range(2100, 2800, 100)] + [(0, '20k')])
        record = self.players_table.FindRecords('id == ' + str(pid))[0]
        rating = float(record.content['rating'])
        newrating = rating + increment
        if newrating < 100:
            newrating = 100
        record.content['rating'] = str(round(newrating, 1))
        record.content['grade'] = self.grades[int(newrating) / 100 * 100]
        print record.content['lastname'], increment
        if not dry_run:
            record.Push()

    def CleanUp(self):
        games = self.games_table.FindRecords('games != ""')
        for row in games:
            row.content['games'] = ''
            row.Push()

    def Publish(self):
        rows = self.players_table.FindRecords('id != ""')
        for row in rows:
            if '.' in row.content['rating']:
                rounded = round(float(row.content['rating']))
                row.content['rating'] = rounded
                row.Push()


class Game:
    """Game class for games played.

    It has the method that computes the rating out of a game result.
    """

    def __init__(self, rating1, rating2, winner, handi=0, tc=1):
        self.rating1 = float(rating1)
        self.rating2 = float(rating2)
        self.winner = float(winner)
        self.handi = int(handi)
        self.tc = float(tc)
        self.CheckParams()

    def CheckParams(self):
        if self.rating1 < 100 or self.rating1 > 2800:
            raise RuntimeError('rating out of range')
        if self.rating2 < 100 or self.rating2 > 2800:
            raise RuntimeError('rating out of range')
        if self.winner not in (self.rating1, self.rating2):
            raise RuntimeError('winner is not one of the players')
        if self.handi < 0 or self.handi > 9:
            raise RuntimeError('improper handicap')
        if self.tc not in [0.5, 0.75, 1.0]:
            raise RuntimeError('improper tournament class')

    def _con(self, rating):
        """Internal function that returns a float as a parameter
        in the computation of ratings.
        """
        index = int(rating) / 100
        conlist = [116, 110, 105, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 51,
                   47, 43, 39, 35, 31, 27, 24, 21, 18, 15, 13, 11, 10, 10]
        return (conlist[index - 1] - (rating - (index * 100)) /
                (100 / (conlist[index - 1] - conlist[index])))

    def Rate(self):
        """
        Computes the player rating.

        See http://www.europeangodatabase.eu/EGD/EGF_rating_system.php
        """
        swapped = False
        #self.rating1 must always be less than self.rating2
        if self.rating1 > self.rating2:
            self.rating1, self.rating2 = self.rating2, self.rating1
            swapped = True
        if self.handi:
            d = self.rating2 - self.rating1 - 100 * (self.handi - 0.5)
        else:
            d = self.rating2 - self.rating1
        a = 200 - ((self.rating2 - d) - 100) / 20
        E = 0.016
        chances1 = 1 / (math.exp(d / a) + 1) - E / 2
        chances2 = 1 - chances1 - E
        if self.winner == self.rating1:
            result1 = 1
            result2 = 0
        else:
            result2 = 1
            result1 = 0
        #There can be only one winner.
        assert result1 + result2 == 1
        new_rating1 = (self.rating1 + self._con(self.rating1) *
                       (result1 - chances1) * self.tc)
        new_rating2 = (self.rating2 + self._con(self.rating2) *
                       (result2 - chances2) * self.tc)
        #Players must not be both gainers or both losers in ratings.
        assert new_rating1 < self.rating1 or new_rating2 < self.rating2
        assert new_rating1 > self.rating1 or new_rating2 > self.rating2
        increment1 = new_rating1 - self.rating1
        increment2 = new_rating2 - self.rating2
        if swapped:
            return increment2, increment1
        else:
            return increment1, increment2


def process_cmdline(argv):
    if argv is None:
        argv = sys.argv[1:]
    parser = optparse.OptionParser(
        formatter=optparse.TitledHelpFormatter(width=78),
        add_help_option=None)
    parser.add_option('-u', '--username')
    parser.add_option('-p', '--password')
    parser.add_option('-a', '--add-player', action='store_true',
                      dest='add_player')
    parser.add_option('--add-player-only', action='store_true',
                      dest='add_player_only')
    parser.add_option('-s', '--sync-ratings', action='store_true',
                      dest='sync_ratings')
    parser.add_option('--sync-ratings-only', action='store_true',
                      dest='sync_ratings_only')
    parser.add_option('-b', '--publish', action='store_true')
    parser.add_option('-d', '--dry-run', action='store_true', dest='dry_run')
    parser.add_option('-r', '--rate', nargs=5,
                      metavar='<rating1> <rating2> <winner> <handi> <tc>')
    parser.add_option('-h', '--help', action='help',
                      help='Show this help message and exit')
    opts, args = parser.parse_args(argv)
    if opts.username is None or opts.password is None:
        parser.error('username and password required')
    if opts.username != 'phgo.ratings@gmail.com':
        parser.error('username incorrect')
    if opts.add_player and opts.add_player_only:
        parser.error('options -a and --add-player-only are mutually exclusive')
    if opts.sync_ratings and opts.sync_ratings_only:
        parser.error(
            'options -s and --sync-ratings-only are mutually exclusive')
    if args:
        parser.error('program takes no command-line arguments; '
                     '"%s" ignored.' % (args,))
    return opts, args


def main(argv=None):
    opts, args = process_cmdline(argv)
    if opts.rate:
        rating1, rating2, winner, handi, tc = opts.rate
        r = Game(rating1, rating2, winner, handi, tc)
        increment1, increment2 = r.Rate()
        print increment1, increment2
        return 0
    phgo = Database(user=opts.username, pasw=opts.password)
    if opts.add_player or opts.add_player_only:
        while True:
            phgo.AddPlayer()
            repeat = raw_input('Enter another player?[y/N]')
            if repeat != 'y':
                if opts.add_player_only:
                    return 0
                break
    if opts.sync_ratings or opts.sync_ratings_only:
        phgo.SyncRatings()
        if opts.sync_ratings_only:
            return 0
    games = phgo.GetGames()
    for pid1, rating1, pid2, rating2, handi, tc in games:
        match = Game(rating1, rating2, winner=rating1, handi=handi, tc=tc)
        increment1, increment2 = match.Rate()
        phgo.UpdateRating(pid1, increment1, opts.dry_run)
        phgo.UpdateRating(pid2, increment2, opts.dry_run)
        if not opts.dry_run:
            phgo.CleanUp()
    if opts.publish:
        if not opts.dry_run:
            phgo.Publish()
    return 0


if __name__ == '__main__':
    status = main()
    sys.exit(status)

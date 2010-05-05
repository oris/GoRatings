#!/usr/bin/env python
#
# Copyright (c) 2010 Benjamin Oris Jr. All rights reserved.

"""Go ratings program.

Computes ELO-based ratings for go players.
"""

import gdata.spreadsheet.text_db
import random
import math

class Database:
    """Provides interface to a database.
    
    The database used now is a Google spreadsheet.
    """
    
    def __init__(self, user=None, pasw=None):
        client = gdata.spreadsheet.text_db.DatabaseClient(username=user,
                    password=pasw)
        db = client.GetDatabases(name='Sid')[0]
        self.players_table = db.GetTables(name='players')[0]
        self.games_table = db.GetTables(name='games')[0]
        # Mapping of ratings to kyu and dan grades.
        self.grades = dict([(x, str(20 - (x-100)/100)+'k')
                 for x in range(100, 2100, 100)] + [(x, str((x - 2000)/100)+'d')
                 for x in range(2100, 2800, 100)] + [(0, '20k')])
    
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
        v = 'n'
        while v != 'y':
            lastname = raw_input('Last name: ')
            firstnames = raw_input('First name(s): ')
            rating = int(raw_input('Rating: '))
            v = raw_input('Are the entries correct?(y/n) ')
        while True:
            newid = str(random.randint(100, 999))
            if not self.players_table.FindRecords('id == ' + str(newid)):
                break
        self.players_table.AddRecord({'id': newid, 'lastname': lastname,
                                         'firstnames': firstnames, 'rating':
                                            str(rating), 'grade':
                                            self.grades[rating]})
        self.games_table.AddRecord({'player': newid, 'baserating':
                                          str(rating)})
    
    def GetRating(self, pid):
        """Get base rating from games worksheet.
        """
        player = self.games_table.FindRecords('player == ' + str(pid))[0]
        return int(player.content['baserating'])
        
    def GetGames(self):
        """Get game results from games worksheet.
        
        Returns a list of tuples: player1, player2, handi, tc
        """
        results = []
        tourney_classes = {'a': 1.0, 'b': 0.75, 'c': 0.5}
        games = self.games_table.FindRecords('games != ""')
        for row in games:
            player1 = row.content['player']
            for g in row.content['games'].split(','):
                game = g.split('+')
                player2 = game[0].strip()
                h = int(game[1][0])
                t = tourney_classes[game[1][1].strip()]
                results.append((player1, player2, h, t))
        return results
        
    def UpdateRating(self, pid, increment):
        record = self.players_table.FindRecords('id == ' + str(pid))[0]
        rating = float(record.content['rating'])
        newrating = rating + increment
        if newrating < 100:
            newrating = 100
        record.content['rating'] = str(round(newrating, 1))
        record.content['grade'] = self.grades[int(newrating)/100*100]
        print record.content['lastname'], increment
        record.Push()
    
    def Publish(self):
        rows = self.players_table.FindRecords('id != ""')
        for row in rows:
            if '.' in row.content['rating']:
                rounded = round(float(row.content['rating']))
                row.content['rating'] = rounded
                row.Push()
    
    
class Player:
    def __init__(self, rating=None, pid=None, db=None):
        """Pass the argument, rating, to test. Pass pid and db arguments
        to retrieve rating from the database.
        
        db must be an instance of Database Class.
        """
        self.rating = float(rating)
        self.pid = str(pid)
        self.db = db
        
        if self.db and not isinstance(self.db, Database):
            raise RuntimeError('There is no Database instance.')
        if self.pid:
            try:
                self.rating = float(self.db.GetRating(self.pid))
            except:
                pass
        if self.rating is None:
            raise RuntimeError(
                'Player has no rating or there is no such player.')
        elif self.rating < 100 or self.rating >= 2800:
            print self.rating
            raise RuntimeError('Rating is out of range.')
            
    def UpdateRating(self, increment):
        self.db.UpdateRating(self.pid, increment)
    
  
class Game:
    """Game class for games played. 
    
    Attributes player1 and player2 may be passed as Player class instances.
        
    Method that computes the rating out of a game result. The equations used
    are from the European Go Federation ratings system. Thanks EGF!
    """
    
    def __init__(self, player1, player2, winner, handi=0, tc=1):
        if isinstance(player1, Player) and isinstance(player2, Player):
            self.rating1 = player1.rating
            self.rating2 = player2.rating
            self.winner = winner.rating
        else:
            self.rating1 = float(player1)
            self.rating2 = float(player2)
            self.winner = float(winner)
        # Number of handicap stones
        self.handi = handi
        # EGF's Tournament Class parameter
        self.tc = tc
    
    def Con(self, rating):
        """Internal function that returns an integer as a parameter
        in the computation of ratings.
        """
        index = int(rating)/100
        conlist = [116, 110, 105, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 51,
                   47, 43, 39, 35, 31, 27, 24, 21, 18, 15, 13, 11, 10, 10]
        return conlist[index-1] - (rating - (index*100)) / \
                    (100/(conlist[index-1]-conlist[index]))
    
    def Rate(self):
        """
        Computes the player rating.
        
        See http://www.europeangodatabase.eu/EGD/EGF_rating_system.php
        """
        swapped = 0
        ra = self.rating1
        rb = self.rating2
        winner = self.winner
        if ra > rb:
            #ra must always be less than rb
            ra, rb = rb, ra    
            swapped = 1
        if self.handi:
            d = rb - ra - 100*(self.handi-0.5)
        else:
            d = rb - ra
        a = 200 - ((rb-d)-100)/20
        E = 0.016
        #winning chances of player1
        sea = 1/(math.exp(d/a)+1) - E/2
        #winning chances of player2
        seb = 1 - sea - E                  
        if winner == ra:
            saa = 1
            sab = 0
        else:
            sab = 1
            saa = 0
        #There can be only one winner.
        assert saa + sab == 1
        #new rating of player1    
        ranew = ra + self.Con(ra)*(saa-sea)*self.tc   
        #new rating of player2
        rbnew = rb + self.Con(rb)*(sab-seb)*self.tc
        #Players must not be both gainers or both losers in ratings.
        assert ranew < ra or rbnew < rb
        assert ranew > ra or rbnew > rb
        if swapped:
            return rbnew-rb, ranew-ra
        else:
            return ranew-ra, rbnew-rb


def main():
    phgo = Database(user='', pasw='')
    games = phgo.GetGames()
    for p1, p2, h, t in games:
        player1, player2 = Player(pid=p1, db=phgo), Player(pid=p2, db=phgo)
        match = Game(player1, player2, winner=player1, handi=h, tc=t)
        increment1, increment2 = match.Rate()
        player1.UpdateRating(increment1)
        player2.UpdateRating(increment2)
        
    
if __name__ == '__main__':
    main()

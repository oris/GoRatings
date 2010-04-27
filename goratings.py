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
    """Database specifies the Google spreadsheet that stores player data.
    
    Methods are for general database management.
    """
    
    def __init__(self, user=None, pasw=None):
        client = gdata.spreadsheet.text_db.DatabaseClient(username=user,
                    password=pasw)
        db = client.GetDatabases(name='Sid')[0]
        self.players_table = db.GetTables(name='players')[0]
        self.games_table = db.GetTables(name='games')[0]
    
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

    
class Player:
    """Player class has the main attribute, rating.
    
    Methods include adding players and updating ratings in the database.
    """
    
    def __init__(self, rating=None, pid=None, db=None):
        """Pass the argument, rating, to test. Pass pid and db arguments
        to retrieve rating from the database.
        
        db must be an instance of Database Class.
        """
        
        self.rating = rating
        self.pid = str(pid)
        self.db = db
        # Mapping of ratings to kyu and dan grades.
        self.grades = dict([(x, str(20 - (x-100)/100)+'k')
                 for x in range(100, 2100, 100)] + [(x, str((x - 2000)/100)+'d')
                 for x in range(2100, 2800, 100)] + [(0, '20k')])
        
        if self.db and not isinstance(self.db, Database):
            raise RuntimeError('There is no Database instance.')
        if self.pid:
            query = 'player == ' + self.pid    
            try:
                record = self.db.games_table.FindRecords(query)[0]   
                self.rating = record.content['baserating']
            except:
                pass
        if self.rating is None:
            raise RuntimeError(
                'Player has no rating or there is no such player.')
        elif self.rating < 100 or self.rating >= 2800:
            raise RuntimeError('Rating is out of range.')
            
    def AddPlayer(self, lastname=None, firstnames=None, rating=None):
        self.pid = str(random.randint(100, 999))
        # TODO: check for existing pid
        self.db.players_table.AddRecord({'id': self.pid, 'lastname': lastname,
                                         'firstnames': firstnames, 'rating':
                                            str(rating), 'grade':
                                            self.grades[rating]})
        self.db.games_table.AddRecord({'player': self.pid, 'baserating':
                                          str(rating)})
        
    def UpdateRating(self, increment):
        query = 'id == ' + self.pid
        record = self.db.players_table.FindRecords(query)[0]
        rating = float(record.content['rating'])
        newrating = rating + increment
        if newrating < 100:
            newrating = 100
        record.content['rating'] = str(round(newrating, 1))
        record.content['grade'] = self.grades[int(newrating)/100*100]
        print record.content['lastname'], increment
        record.Push()

  
class Game:
    """Game class for games played. 
    
    Attributes player1 and player2 must be passed as Player class instances.
    
    Method that computes the rating out of a game result. The equations used
    are from the European Go Federation ratings system. Thanks EGF!
    """
    
    def __init__(self, player1, player2, winner, handi=0, tc=1):
        self.player1 = player1
        self.player2 = player2
        self.winner = winner
        # Number of handicap stones
        self.handi = handi
        # EGF's Tournament Class parameter
        self.tc = tc
    
    def Con(self, rating):
        """Internal function that returns an integer as a parameter
        in the computation of ratings.
        """
        
        conlist = [116, 110, 105, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 51,
                   47, 43, 39, 35, 31, 27, 24, 21, 18, 15, 13, 11, 10, 10]
        return conlist[rating/100-1] - (rating - ((rating/100)*100)) / \
                    (100/(conlist[(rating/100)-1]-conlist[rating/100]))
    
    def Rate(self):
        """
        Computes the player rating.
        """
        
        swapped = 0
        ra = int(self.player1.rating)
        rb = int(self.player2.rating)
        winner = int(self.winner.rating)
        if ra > rb:
            #ra must always be less than rb
            ra, rb = rb, ra    
            swapped = 1
        if self.handi:
            d = rb - ra - 100*(self.handi-0.5)
        else:
            d = rb - ra
        a = 200 - ((rb-d)-100)/20.0
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
        #new rating of player1    
        ranew = ra + self.Con(ra)*(saa-sea)*self.tc   
        #new rating of player2
        rbnew = rb + self.Con(rb)*(sab-seb)*self.tc   
        if swapped:
            return rbnew-rb, ranew-ra
        else:
            return ranew-ra, rbnew-rb


def main():
    phgo = Database(user='phgo.ratings@gmail.com', pasw='')
    tourney_class = {'a': 1.0, 'b': 0.75, 'c': 0.5}
    games = phgo.games_table.FindRecords('baserating != ""')
    for row in games:
        player1 = Player(pid=row.content['player'], db=phgo)
        if row.content['games'] is None: continue
        #Parse the game results
        for g in row.content['games'].split(','):   
            game = g.split('+')
            player2 = Player(pid=game[0].strip(), db=phgo)
            h = int(game[1][0])
            t = tourney_class[game[1][1].strip()]
            match = Game(player1, player2, winner=player1, handi=h, tc=t)
            increment1, increment2 = match.Rate()
            player1.UpdateRating(increment1)
            player2.UpdateRating(increment2)

    
if __name__ == '__main__':
    main()

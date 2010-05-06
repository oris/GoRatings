#!/usr/bin/env python
#
# Copyright (c) 2010 Benjamin Oris Jr. All rights reserved.

"""Go ratings program.

Computes ELO-based ratings for go players.
"""

import gdata.spreadsheet.text_db
import math, random

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
    
    def GetRating(self, player_id):
        """Get base rating from games worksheet.
        """
        player = self.games_table.FindRecords('player == ' + str(player_id))[0]
        return player.content['baserating']
        
    def GetGames(self):
        """Get game results from games worksheet.
        
        Returns a list of tuples.
        """
        results = []
        tourney_classes = {'a': 1.0, 'b': 0.75, 'c': 0.5}
        games = self.games_table.FindRecords('games != ""')
        for row in games:
            player_id1 = row.content['player']
            rating1 = self.GetRating(player_id1) 
            for g in row.content['games'].split(','):
                game = g.split('+')
                player2 = game[0].strip()
                rating2 = self.GetRating(player_id2)
                h = game[1][0]
                t = tourney_classes[game[1][1].strip()]
                results.append((player1, rating1, player2, rating2, h, t))
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
    
    def Con(self, rating):
        """Internal function that returns an integer as a parameter
        in the computation of ratings.
        """
        index = int(rating)/100
        conlist = [116, 110, 105, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 51,
                   47, 43, 39, 35, 31, 27, 24, 21, 18, 15, 13, 11, 10, 10]
        return (conlist[index-1] - (rating - (index*100)) /
                (100/(conlist[index-1]-conlist[index])))
    
    def Rate(self):
        """
        Computes the player rating.
        
        See http://www.europeangodatabase.eu/EGD/EGF_rating_system.php
        """
        swapped = 0
        if self.rating1 > self.rating2:
            #ra must always be less than rb
            self.rating1, self.rating2 = self.rating2, self.rating1    
            swapped = 1
        if self.handi:
            d = self.rating2 - self.rating1 - 100*(self.handi-0.5)
        else:
            d = self.rating2 - self.rating1
        a = 200 - ((self.rating2-d)-100)/20
        E = 0.016
        chances1 = 1/(math.exp(d/a)+1) - E/2
        chances2 = 1 - chances1 - E                  
        if self.winner == self.rating1:
            result1 = 1
            result2 = 0
        else:
            result2 = 1
            result1 = 0
        #There can be only one winner.
        assert result1 + result2 == 1
        new_rating1 = (self.rating1 + self.Con(self.rating1) *
                       (result1-chances1)*self.tc)
        new_rating2 = (self.rating2 + self.Con(self.rating2) *
                       (result2-chances2)*self.tc)
        #Players must not be both gainers or both losers in ratings.
        assert new_rating1 < self.rating1 or new_rating2 < self.rating2
        assert new_rating1 > self.rating1 or new_rating2 > self.rating2
        increment1 = new_rating1 - self.rating1
        increment2 = new_rating2 - self.rating2
        print(a, chances1, chances2, self.Con(self.rating1),
              self.Con(self.rating2))
        if swapped:
            return increment2, increment1
        else:
            return increment1, increment2


def main():
    phgo = Database(user='', pasw='')
    games = phgo.GetGames()
    for player_id1, rating1, player_id2, rating2, handi, tc in games:
        match = Game(rating1, rating2, winner=rating1, handi=handi, tc=tc)
        increment1, increment2 = match.Rate()
        phgo.UpdateRating(player_id1, increment1)
        phgo.UpdateRating(player_id2, increment2)
    
if __name__ == '__main__':
    main()

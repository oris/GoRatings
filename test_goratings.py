"""Unit tests for goratings.py
"""

from goratings import Player, Game
from nose.tools import assert_almost_equal

def rate(rating1, rating2, known_value1, known_value2, h=0):
    player1 = Player(rating1)
    player2 = Player(rating2)
    game = Game(player1, player2, winner=player1, handi=h)
    inc1, inc2 = game.Rate()
    assert_almost_equal(inc1, known_value1, places=2)
    assert_almost_equal(inc2, known_value2, places=2)
    
def test_Rate_equalrating():
    rate(2400, 2400, 7.62, -7.38)
    
def test_Rate_unequalrating():
    rate(320, 400, 63.68, -59.63)
    
def test_Rate_handicap():
    rate(1850, 2400, 25.09, -11.17, h=5)

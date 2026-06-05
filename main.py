import sqlite3
import pandas as pd

# Connect
conn = sqlite3.connect('data/chess.db')

# Load CSVs
dfg = pd.read_csv("data/raw/chess_games.csv", encoding='latin1')
dfp = pd.read_csv("data/raw/chess_players.csv", encoding='latin1')

# Games table
games_df = dfg[['game_id', 'rated', 'turns', 'victory_status', 'winner',
       'time_increment', 'white_id', 'white_rating', 'black_id',
       'black_rating', 'moves', 'opening_code', 'opening_moves',
       'opening_fullname', 'opening_shortname', 'opening_variation']]
games_df.to_sql('games', conn, if_exists='replace', index=False)

openings_df = dfg[['opening_code', 'opening_fullname', 'opening_shortname']].drop_duplicates()
openings_df.to_sql('openings', conn, if_exists='replace', index=False)

players_df = dfp[['username', 'rating_registry', 'total_games_registry']]
players_df.to_sql('players', conn, if_exists='replace', index=False)

# Close connection
conn.close()
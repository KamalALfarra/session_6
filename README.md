# session_6
This is the work for the assignment session 6 of the advanced course 
I have used the initial_db.py Work frame for easier start up and grading 
All of the code is written in the run_assignment method It starts with 12 questions 
from the stages and then proceeds to the last five then saving the feature table 
by just running the file the output would print the results to each question after its number.

Database Schema Documentation

The database is normalized into three tables: **players**, **openings**, and **games**.

The **players** table stores one record per unique player and contains the 
columns `username` (TEXT, Primary Key), `last_rating` (INTEGER), and `total_games` (INTEGER).

The **openings** table stores one record per chess opening and contains 
`opening_code` (TEXT, Primary Key), `opening_shortname` (TEXT), and `opening_fullname` (TEXT).

The **games** table is the central fact table and stores one row per chess game. Its columns include 
`game_id` (INTEGER, Primary Key), `white_id` (TEXT), `black_id` (TEXT), `winner` (TEXT), `victory_status` (TEXT), 
`turns` (INTEGER), `time_increment` (TEXT), `rated` (INTEGER), `opening_code` (TEXT), `white_rating` (INTEGER), 
and `black_rating`(INTEGER).

Foreign key relationships ensure referential integrity. The columns `white_id` and `black_id` 
reference `players.username`, guaranteeing that every player appearing in a game exists in the players table. 
The column `opening_code` references `openings.opening_code`, ensuring that every recorded opening corresponds to a valid opening entry. 




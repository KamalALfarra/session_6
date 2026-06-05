import os
import sqlite3
import logging
import pandas as pd

log = logging.getLogger(__name__)


# Step 0: Create Schema
def create_schema(conn: sqlite3.Connection) -> None:
    """
    We need to create and normalize 3 tables out of the csv data:
    Players, Openings, Games
    
    Define all three tables with explicit types, PRIMARY KEYs,
    FOREIGN KEYs, NOT NULL constraints, and CHECK constraints.

    Why explicit CREATE TABLE instead of letting to_sql() infer?
    - to_sql() creates columns with no constraints whatsoever
    - FK relationships would exist in comments only, not enforced
    - CHECK constraints (winner IN (...), turns >= 1) would be absent
    - NOT NULL would not be set on any column
    - Column types would be SQLite affinity guesses, not intentional choices

    Insertion order matters:
      players and openings must exist before games,
      because games has FK references to both.
    """

    # Drop in reverse FK dependency order so re-runs are clean
    conn.execute("DROP TABLE IF EXISTS games")
    conn.execute("DROP TABLE IF EXISTS openings")
    conn.execute("DROP TABLE IF EXISTS players")


    # Players: one raw per uniqu player. 
    conn.execute("""
        CREATE TABLE players (
            username     TEXT    PRIMARY KEY NOT NULL,
            last_rating  INTEGER NOT NULL,
            total_games  INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Openings: one row per unique opening code.
    conn.execute("""
        CREATE TABLE openings (
            opening_code      TEXT PRIMARY KEY NOT NULL,
            opening_shortname TEXT NOT NULL,
            opening_fullname  TEXT NOT NULL
        )
    """)

    # Games: The core table 
    # White_id and Black_id are foreign keys to players.username
    # Opening_code is a foreign key to openings.opening_code
    # I'm gonna keep the ratings even though in normalzation we can driv them from players. 
    # This is a delibrate de-normalization for analytical convenience.
    conn.execute("""
        CREATE TABLE games (
            game_id        INTEGER PRIMARY KEY NOT NULL,
            white_id       TEXT    NOT NULL
                               REFERENCES players(username),
            black_id       TEXT    NOT NULL
                               REFERENCES players(username),
            winner         TEXT    NOT NULL
                               CHECK(winner IN ('White', 'Black', 'Draw')),
            victory_status TEXT    NOT NULL,
            turns          INTEGER NOT NULL
                               CHECK(turns >= 1),
            time_increment TEXT    NOT NULL,
            rated          INTEGER NOT NULL
                               CHECK(rated IN (0, 1)),
            opening_code   TEXT    NOT NULL
                               REFERENCES openings(opening_code),
            white_rating   INTEGER NOT NULL,
            black_rating   INTEGER NOT NULL
        )
    """)
    
    
    log.info("Schema created: players, openings, games (with FK + CHECK constraints)")


# Step 1: Build Database
def build_tables(conn: sqlite3.Connection, chess: pd.DataFrame) -> None:
    """
    Prepare DataFrames and load them into the pre-defined schema.

    Why to_sql() with if_exists='append' after CREATE TABLE?
    - 'replace' would drop and recreate the table, losing all constraints
    - 'append' inserts rows into the table we already defined
    - This is the correct pattern: define schema explicitly, load data separately

    Insertion order: players → openings → games
    (games has FK references to both; they must exist first)
    """

    # Players: one raw per uniqu player. 
    white = chess[["white_id", "white_rating"]].rename(
        columns={"white_id": "username", "white_rating": "rating"}
    )
    black = chess[["black_id", "black_rating"]].rename(
        columns={"black_id": "username", "black_rating": "rating"}
    )
    players_df = (
        pd.concat([white, black])
        .groupby("username")["rating"]
        .last()
        .reset_index()
        .rename(columns={"rating": "last_rating"})
    )
    # Total games is how many time did they appear as white/black
    white_counts = chess["white_id"].value_counts().rename("w")
    black_counts = chess["black_id"].value_counts().rename("b")
    players_df["total_games"] = (
        players_df["username"]
       .map(white_counts.add(black_counts, fill_value=0))
        .astype(int)
    ) 

    # Turn players into sql table
    players_df.to_sql("players", conn, if_exists="append", index=False)

    log.info(f"Players table: {len(players_df)} rows have been added.")

    # Openings: one row per unique opening code.
    openings_df = (
        chess[["opening_code", "opening_shortname", "opening_fullname"]]
        .drop_duplicates("opening_code")
        .reset_index(drop=True)
    )
    openings_df.to_sql("openings", conn, if_exists="append", index=False)
    log.info(f"Openings table: {len(openings_df)} rows have been added.")

    # Games: The core table 
    # White_id and Black_id are foreign keys to players.username
    # Opening_code is a foreign key to openings.opening_code
    # I'm gonna keep the ratings even though in normalzation we can driv them from players. 
    # This is a delibrate de-normalization for analytical convenience.
    
    games_df = chess[[
        "game_id", "white_id", "black_id", "winner", "victory_status", "turns", "time_increment", 
        "rated", "white_rating", "black_rating", "opening_code",
    ]].copy()
    games_df.to_sql("games", conn, if_exists="append", index=False)
    log.info(f"Games table: {len(games_df)} rows have been added.")

    # Indexes for faster queries on FK columns sice they are a common target for join\where clauses.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_white    ON games(white_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_black    ON games(black_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_opening  ON games(opening_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_winner   ON games(winner)")
    log.info("Indexes created on games(white_id, black_id, opening_code, winner)")


def verify_schema(conn: sqlite3.Connection) -> None:
    """
    Assert expected row counts AND confirm FK/CHECK constraints are present.
    Reads the CREATE TABLE SQL from sqlite_master and checks for key phrases.
    """
    # Row counts
    for table, expected in [("players", 15635), ("openings", 365), ("games", 20058)]:
        actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert actual == expected, f"Expected {expected} rows in {table}, but got {actual}."
        log.info(f"✅ Verified {table} table: {actual} rows.")

    # Constraint verification — read the stored DDL from sqlite_master
    ddl_rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    ddl = {name: sql for name, sql in ddl_rows}

    # players: must have PRIMARY KEY
    assert "PRIMARY KEY" in ddl["players"], "players: missing PRIMARY KEY"

    # openings: must have PRIMARY KEY
    assert "PRIMARY KEY" in ddl["openings"], "openings: missing PRIMARY KEY"

    # games: must have FKs and CHECK constraints
    assert "REFERENCES players" in ddl["games"],  "games: missing FK to players"
    assert "REFERENCES openings" in ddl["games"], "games: missing FK to openings"
    assert "CHECK" in ddl["games"],               "games: missing CHECK constraints"
    assert "winner IN" in ddl["games"],            "games: missing winner CHECK"
    assert "turns >= 1" in ddl["games"],           "games: missing turns CHECK"

    log.info("✓ Schema constraints verified: PKs, FKs, CHECK all present")

    # Verify FK enforcement is active
    fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_status == 1, "PRAGMA foreign_keys is OFF — FKs will not be enforced"
    log.info("✓ PRAGMA foreign_keys = ON confirmed")

def query(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    """Convenience wrapper: SQL → DataFrame."""
    return pd.read_sql(sql, conn)


def run_assignment(conn: sqlite3.Connection) -> None:
    """Stage 1 to 4 then Q1 to Q5"""
    # Make sure ti use the function query we built above! -Hend


def main():
    print("This is for session 6: testing databases")

    # 1. Loadraw chess data
    chess = pd.read_csv(os.path.join("data", "raw", "chess_games.csv"))
    print(f"Loaded chess_games.csv: {chess.shape[0]} rows, {chess.shape[1]} columns.")

    # 2. Build database
    db_path = os.path.join("data", "processed", "chess.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints!! Don't forget this step, otherwise your FK constraints won't work.

    log.info("Creating schema with constraints...")
    create_schema(conn)

    log.info("Building database tables...")
    build_tables(conn, chess)

    verify_schema(conn)

    conn.commit()
    log.info(f"Database tables have been built. {os.path.getsize(db_path)/1024:.2f} KB" )

    # call the asignment function to run the queries
    
    conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()


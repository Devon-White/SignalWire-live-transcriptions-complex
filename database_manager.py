import aiosqlite


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def setup_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    datetime TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    call_id INTEGER,
                    FOREIGN KEY(call_id) REFERENCES calls(id)
                )
            """)
            await db.commit()

    async def insert_transcript(self, date_time, speaker, transcript, call_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO transcripts (datetime, speaker, transcript, call_id) VALUES (?, ?, ?, ?)",
                             (date_time, speaker, transcript, call_id))
            await db.commit()

    async def get_transcripts(self, call_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT datetime, speaker, transcript
                FROM transcripts
                WHERE call_id = ?
            """, (call_id,))
            return await cursor.fetchall()


db_manager = DatabaseManager('transcript.db')

import psycopg2
import psycopg2.extras
import sqlite3
import os
from datetime import datetime, timedelta
import json

class Database:
    def __init__(self):
        self.is_sqlite = False
        # Try DATABASE_URL first (if available and working), then individual params
        database_url = os.getenv('DATABASE_URL')
        
        # Skip the old Neon database completely and use new connection
        if database_url and 'neon' not in database_url:
            try:
                self.connection = psycopg2.connect(database_url)
                self.connection.autocommit = True
                print("Connected using DATABASE_URL")
                self.create_tables()
                return
            except Exception as e:
                print(f"Failed to connect with DATABASE_URL: {e}")
        
        # Try connecting to Replit PostgreSQL with default parameters
        try:
            # Use Replit PostgreSQL defaults
            self.connection = psycopg2.connect(
                host=os.getenv('PGHOST', 'db.local'),
                database=os.getenv('PGDATABASE', 'replit'),
                user=os.getenv('PGUSER', 'replit'),
                password=os.getenv('PGPASSWORD', ''),
                port=os.getenv('PGPORT', '5432')
            )
            self.connection.autocommit = True
            print("Connected to Replit PostgreSQL")
            self.create_tables()
        except Exception as e:
            print(f"PostgreSQL connection failed: {e}")
            print("Falling back to SQLite database")
            try:
                # Fallback to SQLite
                self.connection = sqlite3.connect('bot_database.db', check_same_thread=False)
                self.connection.row_factory = sqlite3.Row
                self.is_sqlite = True
                print("Connected to SQLite database")
                self.create_tables()
            except Exception as e2:
                print(f"SQLite connection also failed: {e2}")
                print("Running bot without database - functionality will be limited")
                self.connection = None
                self.is_sqlite = False

    def _connect(self):
        try:
            if self.connection:
                self.connection.close()
            self.connection = psycopg2.connect(**self.connection_params)
            self.connection.autocommit = True
        except Exception as e:
            print(f"Database connection error: {e}")
            raise

    def _ensure_connection(self):
        if self.connection is None:
            return False
        try:
            if hasattr(self.connection, 'closed') and self.connection.closed:
                return False
            # Test connection
            cursor = self.connection.cursor()
            cursor.execute('SELECT 1')
            cursor.close()
            return True
        except:
            return False
    
    def _placeholder(self):
        """Return the correct parameter placeholder for the database type"""
        return '?' if self.is_sqlite else '%s'

    def create_tables(self):
        if not self._ensure_connection():
            print("Database not available - skipping table creation")
            return
        cursor = self.connection.cursor()
        
        # Users table - compatible with both PostgreSQL and SQLite
        if self.is_sqlite:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    gender TEXT,
                    country TEXT,
                    age INTEGER,
                    agreed_terms INTEGER DEFAULT 0,
                    profile_completed INTEGER DEFAULT 0,
                    is_blocked INTEGER DEFAULT 0,
                    is_vip INTEGER DEFAULT 0,
                    vip_until TEXT,
                    referred_by INTEGER,
                    referral_count INTEGER DEFAULT 0,
                    chat_partner INTEGER,
                    partner_filter TEXT,
                    looking_for_chat INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    gender VARCHAR(10),
                    country VARCHAR(100),
                    age INTEGER,
                    agreed_terms BOOLEAN DEFAULT FALSE,
                    profile_completed BOOLEAN DEFAULT FALSE,
                    is_blocked BOOLEAN DEFAULT FALSE,
                    is_vip BOOLEAN DEFAULT FALSE,
                    vip_until TIMESTAMP,
                    referred_by BIGINT,
                    referral_count INTEGER DEFAULT 0,
                    chat_partner BIGINT,
                    partner_filter VARCHAR(10),
                    looking_for_chat BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        # Admins table
        if self.is_sqlite:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    promoted_by INTEGER,
                    promoted_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id BIGINT PRIMARY KEY,
                    promoted_by BIGINT,
                    promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        # Force join groups table
        if self.is_sqlite:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS force_join_groups (
                    group_id INTEGER PRIMARY KEY,
                    group_link TEXT,
                    added_by INTEGER,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS force_join_groups (
                    group_id BIGINT PRIMARY KEY,
                    group_link VARCHAR(500),
                    added_by BIGINT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        # Chat sessions table
        if self.is_sqlite:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user1_id INTEGER,
                    user2_id INTEGER,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id SERIAL PRIMARY KEY,
                    user1_id BIGINT,
                    user2_id BIGINT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')

        # Message logs table
        if self.is_sqlite:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    message_type TEXT,
                    message_content TEXT,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_logs (
                    id SERIAL PRIMARY KEY,
                    sender_id BIGINT,
                    receiver_id BIGINT,
                    message_type VARCHAR(50),
                    message_content TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        # Bot stats table
        if self.is_sqlite:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_users INTEGER DEFAULT 0,
                    active_chats INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    vip_users INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id SERIAL PRIMARY KEY,
                    total_users INTEGER DEFAULT 0,
                    active_chats INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    vip_users INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        # Insert initial admin
        placeholder = self._placeholder()
        if self.is_sqlite:
            cursor.execute(f'''
                INSERT OR IGNORE INTO admins (user_id) VALUES ({placeholder}) 
            ''', (8147394357,))
        else:
            cursor.execute(f'''
                INSERT INTO admins (user_id) VALUES ({placeholder}) 
                ON CONFLICT (user_id) DO NOTHING
            ''', (8147394357,))

        # Insert initial stats row
        if self.is_sqlite:
            cursor.execute('''
                INSERT OR IGNORE INTO bot_stats (id) VALUES (1) 
            ''')
        else:
            cursor.execute('''
                INSERT INTO bot_stats (id) VALUES (1) 
                ON CONFLICT (id) DO NOTHING
            ''')

        cursor.close()

    def add_user(self, user_id, username=None, first_name=None, last_name=None, referred_by=None):
        if not self._ensure_connection():
            print(f"Database not available - skipping add_user for {user_id}")
            return
        try:
            cursor = self.connection.cursor()
            placeholder = self._placeholder()
            if self.is_sqlite:
                cursor.execute(f'''
                    INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, referred_by)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ''', (user_id, username, first_name, last_name, referred_by))
            else:
                cursor.execute(f'''
                    INSERT INTO users (user_id, username, first_name, last_name, referred_by)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        updated_at = CURRENT_TIMESTAMP
                ''', (user_id, username, first_name, last_name, referred_by))
            cursor.close()
        except Exception as e:
            print(f"Error in add_user: {e}")

    def get_user(self, user_id):
        if not self._ensure_connection():
            # Return a default user structure when database is not available
            return {
                'user_id': user_id,
                'username': None,
                'first_name': None,
                'last_name': None,
                'gender': None,
                'country': None,
                'age': None,
                'agreed_terms': False,
                'profile_completed': False,
                'is_vip': False,
                'vip_until': None,
                'referral_count': 0,
                'partner_filter': None,
                'chat_partner': None,
                'is_blocked': False,
                'referred_by': None,
                'looking_for_chat': False,
                'created_at': None,
                'updated_at': None
            }
        try:
            placeholder = self._placeholder()
            if self.is_sqlite:
                cursor = self.connection.cursor()
                cursor.execute(f'SELECT * FROM users WHERE user_id = {placeholder}', (user_id,))
                user = cursor.fetchone()
                if user:
                    # Convert SQLite row to dict
                    columns = [description[0] for description in cursor.description]
                    result = dict(zip(columns, user))
                    cursor.close()
                    return result
                cursor.close()
                return None
            else:
                cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(f'SELECT * FROM users WHERE user_id = {placeholder}', (user_id,))
                user = cursor.fetchone()
                cursor.close()
                return dict(user) if user else None
        except Exception as e:
            print(f"Error in get_user: {e}")
            return None

    def update_user_terms(self, user_id, agreed):
        if not self._ensure_connection():
            print(f"Database not available - skipping update_user_terms for {user_id}")
            return
        try:
            cursor = self.connection.cursor()
            placeholder = self._placeholder()
            if self.is_sqlite:
                cursor.execute(f'''
                    UPDATE users SET agreed_terms = {placeholder}, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = {placeholder}
                ''', (agreed, user_id))
            else:
                cursor.execute(f'''
                    UPDATE users SET agreed_terms = {placeholder}, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = {placeholder}
                ''', (agreed, user_id))
            cursor.close()
        except Exception as e:
            print(f"Error in update_user_terms: {e}")

    def update_user_profile(self, user_id, gender=None, country=None, age=None):
        if not self._ensure_connection():
            print(f"Database not available - skipping update_user_profile for {user_id}")
            return
        try:
            cursor = self.connection.cursor()
            placeholder = self._placeholder()
            updates = []
            values = []
            
            if gender:
                updates.append(f'gender = {placeholder}')
                values.append(gender)
            if country:
                updates.append(f'country = {placeholder}')
                values.append(country)
            if age:
                updates.append(f'age = {placeholder}')
                values.append(age)
            
            if updates:
                if self.is_sqlite:
                    updates.append('profile_completed = 1')
                else:
                    updates.append('profile_completed = TRUE')
                updates.append('updated_at = CURRENT_TIMESTAMP')
                values.append(user_id)
                
                query = f'UPDATE users SET {", ".join(updates)} WHERE user_id = {placeholder}'
                cursor.execute(query, values)
            cursor.close()
        except Exception as e:
            print(f"Error in update_user_profile: {e}")

    def is_admin(self, user_id):
        if not self._ensure_connection():
            return False
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        cursor.execute(f'SELECT 1 FROM admins WHERE user_id = {placeholder}', (user_id,))
        result = cursor.fetchone()
        cursor.close()
        return result is not None

    def add_admin(self, user_id, promoted_by):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        if self.is_sqlite:
            cursor.execute(f'''
                INSERT OR IGNORE INTO admins (user_id, promoted_by) VALUES ({placeholder}, {placeholder})
            ''', (user_id, promoted_by))
        else:
            cursor.execute(f'''
                INSERT INTO admins (user_id, promoted_by) VALUES ({placeholder}, {placeholder})
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id, promoted_by))
        cursor.close()

    def remove_admin(self, user_id):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        cursor.execute(f'DELETE FROM admins WHERE user_id = {placeholder}', (user_id,))
        cursor.close()

    def get_admins(self):
        if not self._ensure_connection():
            return []
        if self.is_sqlite:
            cursor = self.connection.cursor()
            cursor.execute('SELECT * FROM admins')
            admins = cursor.fetchall()
            if admins:
                columns = [description[0] for description in cursor.description]
                result = [dict(zip(columns, admin)) for admin in admins]
                cursor.close()
                return result
            cursor.close()
            return []
        else:
            cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute('SELECT * FROM admins')
            admins = cursor.fetchall()
            cursor.close()
            return [dict(admin) for admin in admins]

    def add_force_join_group(self, group_id, group_link, added_by):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        if self.is_sqlite:
            cursor.execute(f'''
                INSERT OR REPLACE INTO force_join_groups (group_id, group_link, added_by)
                VALUES ({placeholder}, {placeholder}, {placeholder})
            ''', (group_id, group_link, added_by))
        else:
            cursor.execute(f'''
                INSERT INTO force_join_groups (group_id, group_link, added_by)
                VALUES ({placeholder}, {placeholder}, {placeholder})
                ON CONFLICT (group_id) DO UPDATE SET
                    group_link = EXCLUDED.group_link,
                    added_by = EXCLUDED.added_by,
                    added_at = CURRENT_TIMESTAMP
            ''', (group_id, group_link, added_by))
        cursor.close()

    def remove_force_join_group(self, group_id):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        cursor.execute(f'DELETE FROM force_join_groups WHERE group_id = {placeholder}', (group_id,))
        cursor.close()

    def get_force_join_groups(self):
        if not self._ensure_connection():
            return []
        if self.is_sqlite:
            cursor = self.connection.cursor()
            cursor.execute('SELECT * FROM force_join_groups')
            groups = cursor.fetchall()
            if groups:
                columns = [description[0] for description in cursor.description]
                result = [dict(zip(columns, group)) for group in groups]
                cursor.close()
                return result
            cursor.close()
            return []
        else:
            cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute('SELECT * FROM force_join_groups')
            groups = cursor.fetchall()
            cursor.close()
            return [dict(group) for group in groups]

    def block_user(self, user_id):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        if self.is_sqlite:
            cursor.execute(f'''
                UPDATE users SET is_blocked = 1, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (user_id,))
        else:
            cursor.execute(f'''
                UPDATE users SET is_blocked = TRUE, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (user_id,))
        cursor.close()

    def unblock_user(self, user_id):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        if self.is_sqlite:
            cursor.execute(f'''
                UPDATE users SET is_blocked = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (user_id,))
        else:
            cursor.execute(f'''
                UPDATE users SET is_blocked = FALSE, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (user_id,))
        cursor.close()

    def set_vip_status(self, user_id, days):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        vip_until = datetime.now() + timedelta(days=days)
        if self.is_sqlite:
            cursor.execute(f'''
                UPDATE users SET is_vip = 1, vip_until = {placeholder}, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (vip_until.isoformat(), user_id))
        else:
            cursor.execute(f'''
                UPDATE users SET is_vip = TRUE, vip_until = {placeholder}, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (vip_until, user_id))
        cursor.close()

    def check_vip_expired(self, user_id):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        if self.is_sqlite:
            cursor.execute(f'''
                UPDATE users SET is_vip = 0 
                WHERE user_id = {placeholder} AND datetime(vip_until) < datetime('now')
            ''', (user_id,))
        else:
            cursor.execute(f'''
                UPDATE users SET is_vip = FALSE 
                WHERE user_id = {placeholder} AND vip_until < CURRENT_TIMESTAMP
            ''', (user_id,))
        cursor.close()

    def update_referral_count(self, user_id):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        cursor.execute(f'''
            UPDATE users SET referral_count = referral_count + 1, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = {placeholder}
        ''', (user_id,))
        cursor.close()

    def set_user_looking_for_chat(self, user_id, looking):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        if self.is_sqlite:
            cursor.execute(f'''
                UPDATE users SET looking_for_chat = {placeholder}, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (looking, user_id))
        else:
            cursor.execute(f'''
                UPDATE users SET looking_for_chat = {placeholder}, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = {placeholder}
            ''', (looking, user_id))
        cursor.close()

    def find_chat_partner_by_gender(self, user_id, gender_filter=None):
        if not self._ensure_connection():
            return None
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        
        # Build query based on gender filter
        if gender_filter:
            if self.is_sqlite:
                query = f'''
                    SELECT user_id FROM users 
                    WHERE user_id != {placeholder} 
                    AND chat_partner IS NULL 
                    AND looking_for_chat = 1 
                    AND is_blocked = 0 
                    AND profile_completed = 1 
                    AND gender = {placeholder}
                    AND agreed_terms = 1
                    ORDER BY RANDOM() 
                    LIMIT 1
                '''
            else:
                query = f'''
                    SELECT user_id FROM users 
                    WHERE user_id != {placeholder} 
                    AND chat_partner IS NULL 
                    AND looking_for_chat = TRUE 
                    AND is_blocked = FALSE 
                    AND profile_completed = TRUE 
                    AND gender = {placeholder}
                    AND agreed_terms = TRUE
                    ORDER BY RANDOM() 
                    LIMIT 1
                '''
            cursor.execute(query, (user_id, gender_filter))
        else:
            if self.is_sqlite:
                query = f'''
                    SELECT user_id FROM users 
                    WHERE user_id != {placeholder} 
                    AND chat_partner IS NULL 
                    AND looking_for_chat = 1 
                    AND is_blocked = 0 
                    AND profile_completed = 1 
                    AND agreed_terms = 1
                    ORDER BY RANDOM() 
                    LIMIT 1
                '''
            else:
                query = f'''
                    SELECT user_id FROM users 
                    WHERE user_id != {placeholder} 
                    AND chat_partner IS NULL 
                    AND looking_for_chat = TRUE 
                    AND is_blocked = FALSE 
                    AND profile_completed = TRUE 
                    AND agreed_terms = TRUE
                    ORDER BY RANDOM() 
                    LIMIT 1
                '''
            cursor.execute(query, (user_id,))
        
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None

    def find_chat_partner(self, user_id, gender_filter=None):
        # Legacy method - redirect to new method
        return self.find_chat_partner_by_gender(user_id, gender_filter)

    def start_chat_session(self, user1_id, user2_id):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        
        # Update both users' chat_partner field
        cursor.execute(f'''
            UPDATE users SET chat_partner = {placeholder}, looking_for_chat = {self._boolean_value(False)}, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = {placeholder}
        ''', (user2_id, user1_id))
        
        cursor.execute(f'''
            UPDATE users SET chat_partner = {placeholder}, looking_for_chat = {self._boolean_value(False)}, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = {placeholder}
        ''', (user1_id, user2_id))
        
        # Create chat session record
        cursor.execute(f'''
            INSERT INTO chat_sessions (user1_id, user2_id) 
            VALUES ({placeholder}, {placeholder})
        ''', (user1_id, user2_id))
        
        cursor.close()

    def end_chat_session(self, user_id):
        if not self._ensure_connection():
            return None
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        
        # Get current chat partner
        cursor.execute(f'SELECT chat_partner FROM users WHERE user_id = {placeholder}', (user_id,))
        result = cursor.fetchone()
        
        if not result or not result[0]:
            cursor.close()
            return None
        
        partner_id = result[0]
        
        # End chat session in database
        if self.is_sqlite:
            cursor.execute(f'''
                UPDATE chat_sessions 
                SET ended_at = CURRENT_TIMESTAMP, is_active = 0 
                WHERE (user1_id = {placeholder} OR user2_id = {placeholder}) 
                AND is_active = 1
            ''', (user_id, user_id))
        else:
            cursor.execute(f'''
                UPDATE chat_sessions 
                SET ended_at = CURRENT_TIMESTAMP, is_active = FALSE 
                WHERE (user1_id = {placeholder} OR user2_id = {placeholder}) 
                AND is_active = TRUE
            ''', (user_id, user_id))
        
        # Clear chat_partner for both users
        cursor.execute(f'''
            UPDATE users SET chat_partner = NULL, looking_for_chat = {self._boolean_value(False)}, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = {placeholder}
        ''', (user_id,))
        
        cursor.execute(f'''
            UPDATE users SET chat_partner = NULL, looking_for_chat = {self._boolean_value(False)}, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = {placeholder}
        ''', (partner_id,))
        
        cursor.close()
        return partner_id

    def _boolean_value(self, value):
        return 1 if value and self.is_sqlite else value

    def update_partner_filter(self, user_id, gender_filter):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        cursor.execute(f'''
            UPDATE users SET partner_filter = {placeholder}, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = {placeholder}
        ''', (gender_filter, user_id))
        cursor.close()

    def log_message(self, sender_id, receiver_id, message_type, content):
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        cursor.execute(f'''
            INSERT INTO message_logs (sender_id, receiver_id, message_type, message_content)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
        ''', (sender_id, receiver_id, message_type, content))
        cursor.close()

    def get_bot_stats(self):
        if not self._ensure_connection():
            return {
                'total_users': 0,
                'active_chats': 0,
                'total_messages': 0,
                'vip_users': 0,
                'updated_at': 'N/A'
            }
        
        cursor = self.connection.cursor()
        
        # Get total users
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Get active chats
        if self.is_sqlite:
            cursor.execute('SELECT COUNT(*) FROM users WHERE chat_partner IS NOT NULL')
        else:
            cursor.execute('SELECT COUNT(*) FROM users WHERE chat_partner IS NOT NULL')
        active_chats = cursor.fetchone()[0] // 2  # Divide by 2 since each chat involves 2 users
        
        # Get total messages
        cursor.execute('SELECT COUNT(*) FROM message_logs')
        total_messages = cursor.fetchone()[0]
        
        # Get VIP users
        if self.is_sqlite:
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_vip = 1 AND datetime(vip_until) > datetime("now")')
        else:
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_vip = TRUE AND vip_until > CURRENT_TIMESTAMP')
        vip_users = cursor.fetchone()[0]
        
        cursor.close()
        
        return {
            'total_users': total_users,
            'active_chats': active_chats,
            'total_messages': total_messages,
            'vip_users': vip_users,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def get_all_users(self):
        if not self._ensure_connection():
            return []
        if self.is_sqlite:
            cursor = self.connection.cursor()
            cursor.execute('SELECT user_id FROM users WHERE is_blocked = 0')
            users = cursor.fetchall()
            result = [{'user_id': user[0]} for user in users]
            cursor.close()
            return result
        else:
            cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute('SELECT user_id FROM users WHERE is_blocked = FALSE')
            users = cursor.fetchall()
            cursor.close()
            return [dict(user) for user in users]

    def delete_user(self, user_id):
        """Delete user and all related data"""
        if not self._ensure_connection():
            return
        cursor = self.connection.cursor()
        placeholder = self._placeholder()
        
        # End any active chat first
        self.end_chat_session(user_id)
        
        # Delete from all tables
        cursor.execute(f'DELETE FROM message_logs WHERE sender_id = {placeholder} OR receiver_id = {placeholder}', (user_id, user_id))
        cursor.execute(f'DELETE FROM chat_sessions WHERE user1_id = {placeholder} OR user2_id = {placeholder}', (user_id, user_id))
        cursor.execute(f'DELETE FROM admins WHERE user_id = {placeholder}', (user_id,))
        cursor.execute(f'DELETE FROM users WHERE user_id = {placeholder}', (user_id,))
        
        cursor.close()
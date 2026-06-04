import os
import re
import imaplib
import email
from email.header import decode_header
import pandas as pd
from datetime import datetime, timedelta
import pytz
import sqlite3
from dotenv import load_dotenv

# Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "emails.db")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Init environment variables
load_dotenv(ENV_PATH)

def init_db():
    """Initialize SQLite database for cached emails."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scanned_emails (
            account TEXT,
            date_ist TEXT,
            time_ist TEXT,
            from_str TEXT,
            subject TEXT,
            gmail_link TEXT,
            scanned_at TEXT,
            PRIMARY KEY (account, date_ist, time_ist, from_str, subject, scanned_at)
        )
    """)
    conn.commit()
    conn.close()

def load_config():
    """Load configuration from .env file."""
    # Reload environment to pick up manual modifications
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH, override=True)
        
    config = {
        "lookback_hours": 48,
        "email_1": os.getenv("EMAIL_1") or "",
        "email_1_password": os.getenv("EMAIL_1_PASSWORD") or "",
        "email_2": os.getenv("EMAIL_2") or "",
        "email_2_password": os.getenv("EMAIL_2_PASSWORD") or ""
    }
    
    # Try parsing lookback hours from env if present
    lookback = os.getenv("EMAIL_LOOKBACK_HOURS")
    if lookback and lookback.isdigit():
        config["lookback_hours"] = int(lookback)
        
    return config

def save_config(new_config):
    """Save configuration values to .env file."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    keys_updated = {
        "EMAIL_LOOKBACK_HOURS": False,
        "EMAIL_1": False,
        "EMAIL_1_PASSWORD": False,
        "EMAIL_2": False,
        "EMAIL_2_PASSWORD": False
    }
    
    # Map input keys to env variable keys
    mapping = {
        "lookback_hours": "EMAIL_LOOKBACK_HOURS",
        "email_1": "EMAIL_1",
        "email_1_password": "EMAIL_1_PASSWORD",
        "email_2": "EMAIL_2",
        "email_2_password": "EMAIL_2_PASSWORD"
    }
    
    # Update existing lines
    for i, line in enumerate(lines):
        for conf_key, env_key in mapping.items():
            if line.strip().startswith(env_key + "=") or line.strip().startswith(env_key + " ="):
                if conf_key in new_config:
                    lines[i] = f"{env_key} = \"{new_config[conf_key]}\"\n"
                keys_updated[env_key] = True

    # Append any missing keys
    for conf_key, env_key in mapping.items():
        if not keys_updated[env_key] and conf_key in new_config:
            lines.append(f"{env_key} = \"{new_config[conf_key]}\"\n")
            
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    # Force reload of variables
    load_dotenv(ENV_PATH, override=True)

def save_scanned_emails(emails, scanned_at):
    """Save a list of email records into SQLite DB."""
    if not emails:
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        for em in emails:
            cursor.execute("""
                INSERT OR REPLACE INTO scanned_emails 
                (account, date_ist, time_ist, from_str, subject, gmail_link, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                em.get("account"),
                em.get("date_ist"),
                em.get("time_ist"),
                em.get("from_str"),
                em.get("subject"),
                em.get("gmail_link"),
                scanned_at
            ))
        conn.commit()
    except Exception as e:
        print(f"Error storing emails in database: {e}")
    finally:
        conn.close()

def get_last_scan_emails():
    """Retrieve emails from the latest scan session."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Find the most recent scan timestamp
        cursor.execute("SELECT MAX(scanned_at) FROM scanned_emails")
        row = cursor.fetchone()
        if not row or not row[0]:
            return [], None
            
        last_scanned_at = row[0]
        cursor.execute("""
            SELECT account, date_ist, time_ist, from_str, subject, gmail_link, scanned_at
            FROM scanned_emails
            WHERE scanned_at = ?
            ORDER BY date_ist DESC, time_ist DESC
        """, (last_scanned_at,))
        
        rows = cursor.fetchall()
        emails = []
        for r in rows:
            emails.append({
                "account": r[0],
                "date_ist": r[1],
                "time_ist": r[2],
                "from_str": r[3],
                "subject": r[4],
                "gmail_link": r[5],
                "scanned_at": r[6]
            })
        return emails, last_scanned_at
    except Exception as e:
        print(f"Error retrieving emails from DB: {e}")
        return [], None
    finally:
        conn.close()

def decode_header_string(header_val):
    """Safely decode email header strings."""
    if not header_val:
        return "Unknown"
    try:
        decoded_parts = decode_header(header_val)
        decoded_str = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_str += part.decode(encoding if encoding else "utf-8", errors="replace")
            else:
                decoded_str += part
        return decoded_str
    except Exception:
        return str(header_val)

def scan_emails_pipeline(hours_lookback=48, progress_callback=None):
    """Scan configured Gmail accounts for emails in lookback window."""
    config = load_config()
    accounts = []
    if config["email_1"]:
        accounts.append({"username": config["email_1"], "password": config["email_1_password"]})
    if config["email_2"]:
        accounts.append({"username": config["email_2"], "password": config["email_2_password"]})
        
    ist = pytz.timezone('Asia/Kolkata')
    all_data = []
    
    total_accounts = len(accounts)
    if total_accounts == 0:
        if progress_callback:
            progress_callback("No accounts configured in settings", 0, 0)
        return []

    for index, acc in enumerate(accounts):
        username = acc["username"]
        password = acc["password"]
        
        if progress_callback:
            progress_callback(f"Connecting to {username}...", index, total_accounts)
            
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(username, password)
            mail.select("inbox")
            
            date_since = (datetime.now() - timedelta(hours=hours_lookback)).strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(SINCE "{date_since}")')
            email_ids = messages[0].split()
            
            num_emails = len(email_ids)
            for sub_index, e_id in enumerate(email_ids):
                if progress_callback:
                    progress_callback(f"Fetching {username} email {sub_index+1}/{num_emails}...", index, total_accounts)
                
                res, msg_data = mail.fetch(e_id, "(BODY.PEEK[])")
                for response in msg_data:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        
                        subject = decode_header_string(msg.get("Subject"))
                        subject = re.sub(r'[<>]', '', subject) # Clean subject formatting
                        
                        from_ = decode_header_string(msg.get("From"))
                        
                        date_ = msg.get("Date")
                        if not date_:
                            continue
                            
                        try:
                            email_date = email.utils.parsedate_to_datetime(date_)
                            email_date_ist = email_date.astimezone(ist)
                            date_only = email_date_ist.strftime("%Y-%m-%d")
                            time_only = email_date_ist.strftime("%H:%M:%S")
                        except Exception:
                            # Fallback if parsing fails
                            date_only = datetime.now(ist).strftime("%Y-%m-%d")
                            time_only = datetime.now(ist).strftime("%H:%M:%S")
                            
                        # Use RFC822 Message-ID search query URL for opening the exact email
                        import urllib.parse
                        message_id = msg.get("Message-ID")
                        if message_id:
                            encoded_id = urllib.parse.quote(message_id.strip())
                            gmail_link = f"https://mail.google.com/mail/u/{username}/#search/rfc822msgid%3A{encoded_id}"
                        else:
                            try:
                                msg_id = e_id.decode()
                            except Exception:
                                msg_id = str(e_id)
                            gmail_link = f"https://mail.google.com/mail/u/{username}/#all/{msg_id}"
                        
                        all_data.append({
                            "account": username,
                            "date_ist": date_only,
                            "time_ist": time_only,
                            "from_str": from_,
                            "subject": subject,
                            "gmail_link": gmail_link
                        })
            mail.logout()
        except Exception as e:
            print(f"Error scanning account {username}: {e}")
            if progress_callback:
                progress_callback(f"Error {username}: {str(e)}", index + 1, total_accounts)
                
    # Sort descending by date/time
    all_data.sort(key=lambda x: (x["date_ist"], x["time_ist"]), reverse=True)
    return all_data

def generate_excel_report(emails_list):
    """Write parsed emails list to Excel report."""
    all_rows = []
    for em in emails_list:
        all_rows.append([
            em["account"],
            em["date_ist"],
            em["time_ist"],
            em["from_str"],
            em["subject"],
            em["gmail_link"]
        ])
        
    df = pd.DataFrame(all_rows, columns=[
        "Account",
        "Date (IST)",
        "Time (IST)",
        "From",
        "Subject",
        "Open Email"
    ])
    
    output_path = os.path.join(BASE_DIR, "Email_Report.xlsx")
    df.to_excel(output_path, index=False)
    return output_path

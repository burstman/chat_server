from fastapi import FastAPI, HTTPException
import psycopg2
import json
import spacy
from icecream import ic
import re
import logging
import os

app = FastAPI()
nlp = spacy.load("en_core_web_md")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use environment variables for database credentials
DB_NAME = os.getenv("DB_NAME", "task_manager")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "maison123$")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


def get_usernames():
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT username, user_id FROM users;")
        rows = cursor.fetchall()
        usernames = {row[0].lower(): row[1] for row in rows}
        return usernames
    except Exception as e:
        logger.error(f"Error while fetching usernames: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_projects():
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM projects;")
        rows = cursor.fetchall()
        projects = [row[0].lower() for row in rows]
        return projects
    except Exception as e:
        logger.error(f"Error while fetching projects: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def extract_intent(text: str, syn: dict) -> str:
    doc = nlp(text)
    for token in doc:
        if token.pos_ == "VERB" and (token.dep_ == "ROOT" or token.dep_ == "advcl"):
            for intent, words in syn.items():
                if token.lemma_ in words:
                    return intent
    return ""


def extract_tasks(text: str) -> list[str]:
    tasks = []
    doc = nlp(text)
    task_found = False
    for token in doc:
        if token.lemma_ == "task" and token.dep_ == "compound":
            task_found = True
            head_task = token.head
            tasks.append(head_task.text)
            tasks.extend(
                [child.text for child in head_task.rights if child.dep_ == "conj"]
            )
        elif task_found and token.head.dep_ == "conj":
            tasks.append(token.text)
    return tasks


def extract_users(text: str, user_names: dict) -> tuple[list[int], list[str]]:
    user_ids_list = []
    non_existing_names = []
    doc = nlp(text)
    for token in doc:
        if token.pos_ == "PROPN":
            user_name_lower = token.text.lower()
            if user_name_lower in user_names:
                user_ids_list.append(user_names[user_name_lower])
            else:
                non_existing_names.append(token.text)
    return user_ids_list, non_existing_names


def extract_comment(text: str) -> list[str]:
    pattern = r"\'(.*?)\'"
    matches = re.findall(pattern, text)
    doc = nlp(text)
    for token in doc:
        if token.text == '"':
            doc[token.i] = token.text.replace('"', "'")
    for token in doc:
        if token.lemma_ == "comment":
            return matches
    return []


def extract_projects(text: str) -> list[str]:
    projects = []
    doc = nlp(text)
    project_found = False
    for token in doc:
        if token.lemma_ == "project" and token.dep_ == "compound":
            projects.append(token.head.text)
            project_found = True
        elif project_found and token.dep_ == "conj":
            projects.append(token.text)
    return projects


def extract_deadline_dates(text: str) -> list[str]:
    dates = []
    doc = nlp(text)
    for token in doc:
        if token.text.lower() == "deadline":
            for ent in doc.ents:
                if ent.label_ == "DATE" and ent.start > token.i:
                    dates.append(ent.text)
                    break
    return dates


def connect_to_db(order_dict: dict) -> tuple[str, int]:
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        cursor = conn.cursor()
        insert_query = "INSERT INTO json_data (data) VALUES (%s) RETURNING id;"
        json_str = json.dumps(order_dict)
        cursor.execute(insert_query, (json_str,))
        last_id = cursor.fetchone()[0]
        conn.commit()
        return "Data inserted successfully!", last_id
    except Exception as e:
        logger.error(f"Error while connecting to PostgreSQL: {e}")
        return str(e), -1
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def extract_all(text: str, usernames: dict, projects: dict) -> dict:
    intent_synonyms = {
        "create": ["create", "start", "initiate", "add", "append", "make"],
        "update": ["update", "modify", "edit"],
        "delete": ["delete", "remove", "discard"],
        "assign": ["assign", "attach", "assignment", "attachment"],
        "show": ["list", "show", "display", "view"],
    }
    intent = extract_intent(text, intent_synonyms)
    tasks = extract_tasks(text)
    All_users = extract_users(text, usernames)
    user_ids = All_users[0]
    comments = extract_comment(text)
    projects_mentioned = extract_projects(text)
    print(projects_mentioned)
    deadline = extract_deadline_dates(text)

    # Check for non-existing users
    non_existing_users = [
        user_id for user_id in user_ids if user_id not in usernames.values()
    ]

    # Check for existing projects
    existing_projects = [
        project for project in projects_mentioned if project in projects
    ]
    ic(existing_projects)

    return {
        "intent": intent,
        "tasks": tasks,
        "users": user_ids,
        "comments": comments,
        "projects": projects_mentioned,
        "deadline": deadline,
        "non_existing_users": All_users[1],
        "existing_projects": existing_projects,
    }


users = get_usernames()
ic(users)
projects = get_projects()
ic(projects)


@app.post("/send_data")
def send_data(data: dict):
    ic(data)
    processed_phrase = extract_all(data["message"], users, projects)

    if processed_phrase["non_existing_users"]:
        return {
            "id": 0,
            "message": f"These users do not exist: {', '.join(processed_phrase['non_existing_users'])}",
        }

    if processed_phrase["existing_projects"]:
        return {
            "id": 0,
            "message": f"These projects already exist: {', '.join(processed_phrase['existing_projects'])}",
        }

    if len(processed_phrase["intent"]) == 0:
        return {"id": 0, "message": "Please be more expressive with your order."}

    message = connect_to_db(processed_phrase)
    return {"id": message[1], "message": message[0]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)

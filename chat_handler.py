from fastapi import FastAPI, HTTPException
import psycopg2
import json
import spacy
from icecream import ic
import re

app = FastAPI()
nlp = spacy.load("en_core_web_md")


def get_usernames():
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            dbname="task_manager",
            user="postgres",
            password="maison123$",
            host="localhost",
            port="5432",
        )
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users;")
        rows = cursor.fetchall()
        usernames = [row[0].capitalize() for row in rows]
        return usernames
    except Exception as e:
        print(f"Error while fetching usernames: {e}")
        return []
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
        if token.lemma_ == 'task' and token.dep_ == 'compound':
            task_found = True
            head_task=token.head
            tasks.append(head_task.text)
            for child in list(head_task.rights):
               if child.dep_=="conj":
                tasks.append(child.text)
        elif task_found and token.head.dep_ == 'conj':
            tasks.append(token.text)
    return tasks

def extract_users(text: str, user_names: list[str]) -> list[str]:
    user_names_list = []
    doc = nlp(text)
    for token in doc:
        if token.pos_ == "PROPN" and token.text in user_names:
            user_names_list.append(token.text)
    return user_names_list


def extract_comment(text: str) -> list[str]:
    comments = []
    pattern = r"\"(.*?)\""
    matches = re.findall(pattern, text)
    doc = nlp(text)
    for token in doc:
        if token.lemma_ == "comment":
            comments.extend(matches)
            break
    return comments


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


def connect_to_db(orderDict: dict) -> tuple[str, int]:
    conn = None
    cursor = None
    try:
        conn_str = {
            "dbname": "task_manager",
            "user": "postgres",
            "password": "maison123$",
            "host": "localhost",
            "port": "5432",
        }
        print(f"Connecting to DB with: {conn_str}")  # Debugging print

        conn = psycopg2.connect(**conn_str)
        cursor = conn.cursor()
        insert_query = "INSERT INTO json_data (data) VALUES (%s) RETURNING id;"
        json_str = json.dumps(orderDict)
        cursor.execute(insert_query, (json_str,))
        last_id = cursor.fetchone()[0]
        conn.commit()
        return ("Data inserted successfully!", last_id)
    except Exception as e:
        print(f"Error while connecting to PostgreSQL: {e}")
        return (str(e), -1)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def extract_all(text: str, usernames: list[str]) -> dict:
    intent_synonyms = {
        "create": ["create", "start", "initiate", "add", "append", "make"],
        "update": ["update", "modify", "edit"],
        "delete": ["delete", "remove", "discard"],
        "assign": ["assign", "attach", "assignment", "attachement"],
        "show": ["list", "show", "display", "view"],
    }
    intent = extract_intent(text, intent_synonyms)
    tasks = extract_tasks(text)
    users = extract_users(text, usernames)
    comments = extract_comment(text)
    projects = extract_projects(text)
    deadline = extract_deadline_dates(text)

    return {
        "intent": intent,
        "tasks": tasks,
        "users": users,
        "comments": comments,
        "projects": projects,
        "deadline": deadline,
    }
users = get_usernames()

@app.post("/send_data")
def send_data(data: dict):
    ic(data)
    
    processed_phrase = extract_all(data["message"], users)
    message = connect_to_db(processed_phrase)
    return {"id": message[1], "message": message[0]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)

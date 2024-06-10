from fastapi import FastAPI, HTTPException
import psycopg2
import json
import spacy
from icecream import ic
import re
import logging
import os
from typing import List, Tuple, Dict, Optional

app = FastAPI()
nlp = spacy.load("en_core_web_md")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use environment variables for database credentials
DB_NAME = os.getenv("DB_NAME", "task_manager")
DB_USER = os.getenv("DB_USER", "burstman")
DB_PASSWORD = os.getenv("DB_PASSWORD", "maison123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


def get_usernames():
    try:
        with psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT username, user_id FROM users;")
                rows = cursor.fetchall()
                usernames = {row[0].lower(): row[1] for row in rows}
                return usernames
    except Exception as e:
        logger.error(f"Error while fetching usernames: {e}")
        return {}


def get_projects():
    try:
        with psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT name FROM projects;")
                rows = cursor.fetchall()
                projects = [row[0].lower() for row in rows]
                return projects
    except Exception as e:
        logger.error(f"Error while fetching projects: {e}")
        return []


def extract_intent(text: str, syn: dict) -> str:
    doc = nlp(text)
    for token in doc:
        if token.pos_ == "VERB" and (token.dep_ == "ROOT" or token.dep_ == "advcl"):
            for intent, words in syn.items():
                if token.lemma_ in words:
                    return intent
    return ""


def extract_tasks(text: str) -> List[str]:
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


def extract_users(text: str, user_names: dict) -> Tuple[List[str], List[str]]:
    user_names_list = []
    non_existing_names = []
    doc = nlp(text)
    for token in doc:
        if token.pos_ == "PROPN":
            user_name_lower = token.text.lower()
            ic(user_name_lower)
            if user_name_lower in user_names:
                user_names_list.append(user_name_lower)
            else:
                non_existing_names.append(token.text)
    return (user_names_list, non_existing_names)


def extract_comment(text: str) -> list:
    comments = []
    pattern = r"\'(.*?)\'"
    matches = re.findall(pattern, text)
    doc = nlp(text)

    for token in doc:
        if token.lemma_ == "comment":
            comments.extend(matches)
            break  # Stop processing after finding the first occurrence of "comment"

    return comments


def extract_description(text: str) -> list:
    descriptions = []
    pattern = r"\'(.*?)\'"
    matches = re.findall(pattern, text)
    doc = nlp(text)

    for token in doc:
        if token.lemma_ == "description":
            descriptions.extend(matches)
            break  # Stop processing after finding the first occurrence of "comment"

    return descriptions


def extract_projects(text: str) -> List[str]:
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


def extract_deadline_dates(text: str) -> List[str]:
    dates = []
    doc = nlp(text)
    deadline_index = None

    # Find the index of the token containing "deadline"
    for i, token in enumerate(doc):
        if token.text.lower() == "deadline":
            deadline_index = i
            break

    # If "deadline" is found, check for dates after it using regex
    if deadline_index is not None:
        # Combine tokens into a single text
        remaining_text = " ".join([token.text for token in doc[deadline_index + 1 :]])
        # Search for dates using regex
        date_matches = re.findall(
            r"(?<!\d)(?:(?:0?[1-9]|[12][0-9]|3[01])[\/\-](?:0?[1-9]|1[012])[\/\-]\d{4})(?!\d)",
            remaining_text,
        )
        # Append matches to dates list
        dates.extend(date_matches)

    return dates


def connect_to_db(order_dict: dict) -> Tuple[str, int]:
    try:
        with psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        ) as conn:
            with conn.cursor() as cursor:
                insert_query = "INSERT INTO json_data (data) VALUES (%s) RETURNING id;"
                json_str = json.dumps(order_dict)
                ic(json_str)
                cursor.execute(insert_query, (json_str,))
                last_id = cursor.fetchone()[0]
                conn.commit()
                return "Data inserted successfully!", last_id
    except Exception as e:
        logger.error(f"Error while connecting to PostgreSQL: {e}")
        return str(e), -1


def extract_all(text: str, usernames: dict, projects: List[str]) -> dict:
    intent_synonyms = {
        "create": ["create", "start", "initiate", "add", "append", "make"],
        "update": ["update", "modify", "edit", "set"],
        "delete": ["delete", "remove", "discard"],
        "assign": ["assign", "attach", "assignment", "attachment"],
        "show": ["give", "list", "show", "display", "view"],
        "describe": ["description", "describe"],
    }
    intent = extract_intent(text, intent_synonyms)
    tasks = extract_tasks(text)
    All_users = extract_users(text, usernames)
    ic(All_users)
    user_ids = All_users[0]
    comments = extract_comment(text)
    ic(comments)
    projects_mentioned = extract_projects(text)
    ic(projects_mentioned)
    deadline = extract_deadline_dates(text)
    description = extract_description(text)

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
        "description": description,
    }


def fetch_and_format_data():
    try:
        with psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        ) as conn:
            with conn.cursor() as cur:
                query = """
                SELECT
                    p.project_id, p.name AS project_name, p.description AS project_description, p.created_at AS project_created_at, p.created_by AS project_creator_id, pc.username AS project_creator_username, pc.email AS project_creator_email,
                    t.task_id, t.title AS task_title, t.description AS task_description, t.status AS task_status, t.due_date AS task_due_date, t.created_at AS task_created_at, t.created_by AS task_creator_id, tc.username AS task_creator_username, tc.email AS task_creator_email,
                    COUNT(DISTINCT tua.user_id) + COUNT(DISTINCT c.user_id) AS num_affected_users,
                    tua.user_id AS assigned_user_id, tua.username AS assigned_username, tua.email AS assigned_email,
                    c.comment_id, c.user_id AS comment_user_id, cu.username AS comment_username, cu.email AS comment_email, c.comment_text, c.created_at AS comment_created_at
                FROM
                    projects p
                LEFT JOIN
                    users pc ON p.created_by = pc.user_id
                LEFT JOIN
                    tasks t ON p.project_id = t.project_id
                LEFT JOIN
                    users tc ON t.created_by = tc.user_id
                LEFT JOIN
                    attachments a ON t.task_id = a.task_id
                LEFT JOIN
                    users tua ON a.uploaded_by = tua.user_id
                LEFT JOIN
                    comments c ON t.task_id = c.task_id
                LEFT JOIN
                    users cu ON c.user_id = cu.user_id
                GROUP BY
                    p.project_id, p.name, p.description, p.created_at, p.created_by, pc.username, pc.email,
                    t.task_id, t.title, t.description, t.status, t.due_date, t.created_at, t.created_by, tc.username, tc.email,
                    tua.user_id, tua.username, tua.email,
                    c.comment_id, c.user_id, cu.username, cu.email, c.comment_text, c.created_at
                ORDER BY
                    p.project_id, t.task_id, c.comment_id;
                """

                cur.execute(query)
                results = cur.fetchall()

        # Transforming data into a text paragraph
        paragraph = ""
        current_project = None
        current_task = None

        for row in results:
            (
                project_id,
                project_name,
                project_description,
                project_created_at,
                project_creator_id,
                project_creator_username,
                project_creator_email,
                task_id,
                task_title,
                task_description,
                task_status,
                task_due_date,
                task_created_at,
                task_creator_id,
                task_creator_username,
                task_creator_email,
                num_affected_users,
                assigned_user_id,
                assigned_username,
                assigned_email,
                comment_id,
                comment_user_id,
                comment_username,
                comment_email,
                comment_text,
                comment_created_at,
            ) = row

            if project_id != current_project:
                if current_project is not None:
                    paragraph += "\n\n"
                paragraph += f"Project '{project_name}' (ID: {project_id}): {project_description}, created on {project_created_at} by {project_creator_username} ({project_creator_email}).\n"
                current_project = project_id
                current_task = None

            if task_id and task_id != current_task:
                paragraph += f"  Task '{task_title}' (ID: {task_id}): {task_description}, status: {task_status}, due: {task_due_date}, created on {task_created_at} by {task_creator_username} ({task_creator_email}).\n"
                paragraph += f"    Number of affected users: {num_affected_users}\n"
                if assigned_user_id:
                    paragraph += (
                        f"    Assigned to: {assigned_username} ({assigned_email}).\n"
                    )
                current_task = task_id

            if comment_id:
                paragraph += f"    Comment by {comment_username} ({comment_email}) on {comment_created_at}: {comment_text}\n"
        ic(paragraph)
        return paragraph
    except Exception as e:
        logger.error(f"Error while fetching and formatting data: {e}")
        return ""


def get_most_similar_response(paragraph, query):
    nlp = spacy.load("en_core_web_lg")

    paragraph = " ".join(paragraph.split())
    paragraph = paragraph.strip().replace("'", "")

    doc = nlp(paragraph)
    query_doc = nlp(query)

    sentences = list(doc.sents)
    max_similarity = -1
    most_similar_sentence = ""

    for sent in sentences:
        similarity = query_doc.similarity(sent)
        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_sentence = sent.text

    return most_similar_sentence


def store_chat_message(data: dict) -> int:
    try:
        with psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        ) as conn:
            with conn.cursor() as cursor:
                insert_query = (
                    "INSERT INTO chat_messages (data) VALUES (%s) RETURNING id;"
                )
                json_data = json.dumps(data)
                cursor.execute(insert_query, (json_data,))
                chat_id = cursor.fetchone()[0]
                conn.commit()
                return chat_id
    except Exception as e:
        logger.error(f"Error while storing chat message: {e}")
        return -1


users = get_usernames()
ic(users)
projects = get_projects()
ic(projects)


@app.post("/send_data")
def send_data(data: dict):
    ic(data)
    processed_phrase = extract_all(data["message"], users, projects)

    if len(processed_phrase["intent"]) == 0:
        formatted_text = fetch_and_format_data()
        most_similar_response = get_most_similar_response(
            formatted_text, data["message"]
        )
        if len(most_similar_response) > 0:
            return {"id": 0, "message": most_similar_response}
        else:
            return {"id": 0, "message": "Sorry, I didn't understand you."}

    message = connect_to_db(processed_phrase)

    ic(message[1])
    return {"id": message[1], "message": message[0]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)

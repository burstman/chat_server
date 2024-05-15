from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import json
from icecream import ic
# from typing import Any

app = FastAPI()


# Connect to PostgreSQL


def connect_to_db(orderDict: dict):
    db_params = {
        'host': 'localhost',
        'database': 'postgres',
        'user': 'postgres',
    }

    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Define the SQL statement to insert JSON data
        insert_query = "INSERT INTO orderIn_json (data) VALUES (%s);"

        # Convert JSON data to string
        json_str = json.dumps(orderDict)

        # Execute the SQL statement
        cursor.execute(insert_query, (json_str,))

        # Commit the transaction
        conn.commit()
        print("Data inserted successfully!")

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)
        error_message = str(error)
        return error_message.split("\n")[0]

    finally:
        # Close database connection
        if conn:
            cursor.close()
            conn.close()
            print("PostgreSQL connection is closed.")


@app.post("/send_data")
def send_data(data: dict):
    print(data)
    message = connect_to_db(dict(data))

    return {"message": message}

    # return {"message": "Data received and processed successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)

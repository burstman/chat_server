from fastapi import FastAPI, HTTPException
import psycopg2
import json

app = FastAPI()

# Connect to PostgreSQL
def connect_to_db():
    try:
        db_params = {
            'host': 'localhost',
            'database': 'postgres',
            'user': 'postgres',
        }
        conn = psycopg2.connect(**db_params)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except psycopg2.Error as e:
        print("Error connecting to PostgreSQL:", e)
        return None

# Function to handle messages from trigger function
def handle_trigger_message(trigger_message):
    # Add your logic here to handle the trigger message
    print("Received trigger message:", trigger_message)

# Listen to messages from PostgreSQL
def listen_to_messages():
    conn = connect_to_db()
    if conn is None:
        return

    try:
        cur = conn.cursor()
        cur.execute("LISTEN order_event;")

        print("Listening for messages in channel:", "order_event")

        while True:
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                handle_trigger_message(notify.payload)

    except psycopg2.Error as e:
        print("Error listening to messages:", e)
    finally:
        if conn is not None:
            conn.close()

@app.post("/send_data")
def send_data(data):
    print(data)

    # Connect to PostgreSQL and insert data
    conn = connect_to_db()
    if conn is None:
        raise HTTPException(
            status_code=500, detail="Error connecting to database")

    try:
        cur = conn.cursor()

        # Convert the data to JSON string
        json_data = json.dumps(data)
        cur.execute(
            "INSERT INTO orderin_json (data) VALUES (%s);",
            (json_data,)
        )
        conn.commit()
        print("Data inserted into PostgreSQL")
    except (Exception, psycopg2.Error) as e:
        print("Error inserting data into PostgreSQL:", e)
        raise HTTPException(
            status_code=500, detail="Error inserting data into database")
    finally:
        if conn is not None:
            cur.close()
            conn.close()
            print("Connection closed")

    # If no error occurred, return a success message
    return {"message": "Data received and processed successfully"}

# Start listening for trigger messages
listen_to_messages()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)

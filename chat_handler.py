from fastapi import FastAPI
import psycopg2
import json
import spacy
from icecream import ic


app = FastAPI()


# Connect to PostgreSQL

def word2int(numword) -> int:
    num = 0
    try:
        num = int(numword)
        return num
    except ValueError:
        pass
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
             "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
    for idx, word in enumerate(words):
        if word in numword:
            num = idx
    return num



    # Processes a given phrase and extracts relevant order information, such as the product, type, and quantity.
    # Args: phrase (str): The input phrase to be processed.
    # Returns: dict: A dictionary containing the extracted order information, with keys 'product', 'type', and 'qty'.

def process_phrase(phrase: str) -> dict:
 
    nlp = spacy.load('en_core_web_sm')
    doc = nlp(phrase)
    orderdict = {}
    for token in doc:
        if token.dep_ == 'dobj':
            # print(token.head.text + token.text.capitalize())
            dobj = token
            print(list(dobj.lefts))
            orderdict.update(product=dobj.lemma_)
            for child in dobj.lefts:
                if child.dep_ == 'amod' or child.dep_ == 'compound':
                    orderdict.update(type=child.text)
                elif child.dep_ == 'det':
                    orderdict.update(qty=1)
                elif child.dep_ == 'nummod':
                    orderdict.update(qty=word2int(child.text))
            break
    return orderdict


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
        return "Data inserted successfully!"

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)
        error_message = str(error)
        return error_message.split("\n")[0]

    finally:
        # Close database connection
        if conn:
            cursor.close()
            conn.close()
           


@app.post("/send_data")
def send_data(data: dict):
    ic(data)
    proccessed_phrase =process_phrase(data["message"])
    message = connect_to_db(proccessed_phrase)

    return {"message": message}

    # return {"message": "Data received and processed successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)

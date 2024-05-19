from fastapi import FastAPI
import spacy


app = FastAPI()


def word2int(numword):
    num = 0
    try:
        num = int(numword)
        return num
    except ValueError:
        pass
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven",
             "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
             "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
    for idx, word in enumerate(words):
        if word in numword:
            num = idx
    return num


# Global variable to store the request data
request_data = {}

# Define a function to update the request_data


def update_request_data(data: dict):
    global request_data
    request_data = data
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(request_data["message"])
    orderDict = {}
    for token in doc:
        if token.dep_ == 'dobj':
            # print(token.head.text + token.text.capitalize())
            dobj = token
            print(list(dobj.lefts))
            orderDict.update(product=dobj.lemma_)
            for child in dobj.lefts:
                if child.dep_ == 'amod' or child.dep_ == 'compound':
                    orderDict.update(type=child.text)
                elif child.dep_ == 'det':
                    orderDict.update(qty=1)
                elif child.dep_ == 'nummod':
                    orderDict.update(qty=word2int(child.text))
            break
    print(orderDict)
    return orderDict

# Endpoint to handle POST requests


@app.post("/process_data/")
def process_data(data: dict):
    # Update the request_data using the function
    order=update_request_data(data)
    return order

# Endpoint to access the stored request data


@app.get("/get_data/")
def get_data():
    return request_data

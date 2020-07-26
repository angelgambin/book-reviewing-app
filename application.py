import os 

from flask import Flask, session, render_template, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import requests
import json

app = Flask(__name__)

# Check for environment variable
if not os.getenv("SQLALCHEMY_DATABASE_URI"):
    raise RuntimeError("SQLALCHEMY_DATABASE_URI is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"))
db = scoped_session(sessionmaker(bind=engine))

# welcome page

@app.route("/")
def index():
    if "uid" in session:
        return render_template("booksearch.html", session = session)
    else:
        return render_template("index.html", session = session)

# log in page

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    userRecord = db.execute("SELECT * FROM users WHERE email = :email", {"email": email}).fetchone()

    if userRecord is None:
        return render_template("index.html", message="Email error, please try again", session = session)
    
    # checks password validity

    row = dict(userRecord)
    if row["password"] != password:
        return render_template("index.html", message="Password error, please try again", session = session)

    session["uid"] = row["id"]
    session["email"] = row["email"]

    return render_template("booksearch.html", session = session)

# log out page

@app.route("/logout")
def logout():
    if "uid" in session:
        del session["uid"]
    return render_template("index.html")   

# registration process page

@app.route("/registration", methods=["POST"])
def registration():
    return render_template("registration.html")

# new user page 

@app.route("/newuser", methods=["POST"])
def newuser():

    email = request.form.get("email")
    password = request.form.get("password")
    firstname = request.form.get("firstname")
    lastname = request.form.get("lastname")

    if db.execute("SELECT * FROM users WHERE email = :email", {"email": email}).rowcount != 0:
        return render_template("registration.html", message=f"Email address {email} is being used already.")

    db.execute("INSERT INTO users (email, password, firstname, lastname) VALUES (:email, :password, :firstname, :lastname)",
            {"email":email, "password":password, "firstname":firstname, "lastname":lastname})
    db.commit()
    return render_template("index.html")

# book search page

@app.route("/search", methods=["POST"])
def search():
    if not "uid" in session:
        return render_template("index.html")
    searchBy = request.form.get("searchBy")
    info = request.form.get("info").strip() + "%"
    result = db.execute(f"SELECT * FROM books WHERE {searchBy} like :{searchBy}", {f"{searchBy}": info }).fetchall()
    return render_template("booksearchresults.html", results=result)

# book information page

@app.route("/bookpage", methods=["GET"])
def bookinfo(isbn = ""):
    if not "uid" in session:
        return render_template("index.html")
    if not isbn:
        isbn = request.args["isbn"]
    bookinfo = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn }).fetchone()
    goodreads = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "enter your api key here", "isbns": isbn})
    reviews = db.execute("SELECT text, rating, firstname, lastname, email FROM reviews JOIN users on reviews.userid = users.id WHERE isbn = :isbn and not userid = :userid", {"isbn": isbn, "userid":session["uid"] }).fetchall()
    myreview = db.execute("SELECT * FROM reviews WHERE isbn = :isbn and userid = :userid", {"isbn": isbn, "userid": session["uid"] }).fetchone()
    return render_template("bookpage.html", results=bookinfo, goodreads=goodreads.json(), reviews = reviews, myreview = myreview)

#  book reviews page

@app.route("/review", methods=["POST"])
def review():
    if not "uid" in session:
        return render_template("index.html")
    reviewText = request.form.get("review").strip()
    reviewRating = request.form.get("rating").strip()
    isbn = request.form.get("isbn").strip()
    print(f"review={reviewText} isbn={isbn}")
    myreview = db.execute("SELECT * FROM reviews WHERE isbn = :isbn and userid = :userid", {"isbn": isbn, "userid": session["uid"]}).fetchone()
    if myreview:
        db.execute("UPDATE reviews SET text = :text WHERE isbn = :isbn and userid = :userid", {"text": reviewText, "isbn": isbn, "userid": session["uid"]})
        db.execute("UPDATE reviews SET rating = :rating WHERE isbn = :isbn and userid = :userid", {"rating": reviewRating, "isbn": isbn, "userid": session["uid"]})
    else:
        db.execute("INSERT INTO reviews (isbn, userid, text, rating) VALUES (:isbn, :userid, :text, :rating)", {"isbn": isbn, "userid": session["uid"], "text": reviewText, "rating": reviewRating})
    db.commit()
    return bookinfo(isbn)

# API goodreads page

@app.route("/api/<isbn>", methods=["GET"])
def api(isbn):
    bookinfo = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn }).fetchone()
    if bookinfo:
        bookinfo = dict(bookinfo)
        goodreads = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "enter your api key here", "isbns": isbn}).json()
        
        bookinfo["review_count"] = goodreads["books"][0]["work_ratings_count"]
        bookinfo["average_score"] = goodreads["books"][0]["average_rating"]
        return json.dumps(bookinfo)
    else:
        return render_template("error.html"), 404

        
#!/usr/bin/python
from re import compile, findall, split, S
from os import getenv
from os.path import join, dirname, splitext
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv
from flask import Flask, render_template, url_for, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from mariadb.connector import connect
from textract import process
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# Create the .env file's path and load it
load_dotenv(join(dirname(__file__), ".env"))

conn = connect(
	host=getenv("DB_Host"),
	user=getenv("DB_User"),
	passwd=getenv("DB_Pass"),
	database=getenv("DB_Db")
)

cursor = conn.cursor(dictionary=True)

def database():
	cursor.execute("SELECT COUNT(*) AS num FROM questions")
	res = cursor.fetchone()
	return res["num"]

def logged(required_type = 0):
	def decorator(func):
		def inner():
			if "logged_user" in session:
				if database():
					user_type = 0
					if required_type > 0:
						cursor.execute("SELECT type FROM users where id=%s", (session["logged_user"],))
						user_type = cursor.fetchone()
					if user_type >= required_type:
						func()
					else:
						return "Permission denied"
				else:
					return redirect(url_for("setup"))
			else:
				return redirect(url_for("login"))
		return inner
	return decorator

def get(i):
	cursor.execute("SELECT question FROM questions WHERE id=%s", (i,))
	qa = [cursor.fetchone()]

	cursor.execute("SELECT answer FROM answers WHERE q_id=%s", (i,))
	for answer in cursor.fetchall():
		qa.append(answer)

	return qa

app = Flask(__name__)
app.secret_key = getenv("Cookie_secret")

@app.route("/")
@logged()
def index():
	return redirect(url_for("test"))

@app.route("/login", methods=["GET", "POST"])
def login():
	if request.method == "GET":
		return render_template('login.html')

	form = request.form;
	cursor.execute("SELECT * FROM users WHERE username=%s", (form["email"],))
	user = cursor.fetchone()

	if user == None:
		flash("Wrong username")
		return render_template("login.html")

	if check_password_hash(user["password"], form["password"]):
		session["logged_user"] = str(user)
		return redirect(url_for("studenti"))
	else:
		flash("Wrong password")
		return render_template("login.html")

@app.route("/register", methods=["POST"])
def register():
	form = request.form
	values = (form["username"], generate_password_hash(form["password"]))
	cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", values)
	conn.commit()
	return redirect(url_for("test"))

@app.route("/logout")
def logout():
	session.pop("logged_user", None)
	return redirect(url_for("login"))

@app.route("/setup", methods=["GET", "POST"])
@logged(1)
def setup():
	if request.method == "GET":
		return render_template("setup.html")

	#if request:
	#cursor.execute("TRUNCATE TABLE questions;TRUNCATE TABLE answers;")
	#conn.commit()
	
	if request.files:
		with NamedTemporaryFile() as file:
			question=compile(r"\d+\. *(.+)", S)
			answer=compile(r"[a-zа-ш]\) *(.+?)(?=\n\n|$|[a-zа-ш]\))", S) #Todo:Fix a. b. ... question format
			clean=compile(r"[ \n][ \n]+")
			for name in request.files:
				upload = request.files[name]
				upload.save(file)
				file.flush()
				text = process(file.name, extension=splitext(upload.filename)[1][1:])

				i = database()-1
				for chunk in split(r"\n[ \t]*(?=[a-zа-ш\d]+[).])", text):
					if m := question.match(chunk):
						i += 1
						question = clean.sub(" ", m.group(1))
						cursor.execute("INSERT INTO questions (question) VALUES (%s)", (question,))
					elif m := answer.match(chunk):
						answer = clean.sub(" ", m.group(1))
						cursor.execute("INSERT INTO answers (q_id, answer) VALUES (%s, %s)", (i, answer))
				conn.commit()

	flash("Zahtev uspešno obrađen")
	return render_template("setup.html")

num = -1
@app.route("/draw", methods=["GET", "POST"])
@logged(1)
def draw():
	if request.method == "GET":
		return render_template("draw.html")

	global num
	br = 0
	form = request.form
	mo = findall("r\d", form["input"])
	c = canvas.Canvas(join("static", str(num+1)+".pdf"), A4)
	tobject = c.beginText(2*cm, A4[1]-2*cm) #2cm~=56.693

	if len(mo):
		for i in mo:
			tobject.textLine(get(i))
		br = 1

	try:
		for i in range(int(form["start"]), int(form["end"])+1, int(form["iterator"])):
			tobject.textLine(get(i))
		br = 1
	except ValueError:
		pass

	if br:
		c.drawText(tobject)
		c.showPage()
		c.save()
		num += 1
		return app.send_static_file(str(num)+".pdf")

	flash("Morate popuniti neko polje")
	return render_template("draw.html")

app.run()

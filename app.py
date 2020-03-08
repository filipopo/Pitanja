#!/usr/bin/python
from re import compile
from os import getenv
from os.path import join,dirname
from dotenv import load_dotenv
from flask import Flask, render_template, url_for, request, redirect, flash
from mysql.connector import connect
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
 
# Create .env file path and load it
load_dotenv(join(dirname(__file__), '.env'))

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

def get(i):
	cursor.execute("SELECT question FROM questions WHERE id=%s",(i,))
	res=cursor.fetchone()
	return res

app = Flask(__name__)
app.secret_key = getenv("Cookie_secret")

@app.route("/")
def index():
	if database(): return redirect(url_for("draw"))
	return redirect(url_for("setup"))

@app.route("/setup", methods=["GET", "POST"])
def setup():
	if request.method == "GET":
		return render_template("setup.html")

	f = request.form["file"]
	lines = f.readlines()
	for line in lines:
		cursor.execute("INSERT INTO questions (question) VALUES %s", (line,))
		conn.commit()

num=0
@app.route("/draw", methods=["GET", "POST"])
def draw():
	if request.method == "GET":
		return render_template("draw.html")

	br=0
	global num
	form=request.form
	mo=compile(r"\d").findall(form["input"])
	c = canvas.Canvas(join("static",str(num)+".pdf"),A4)
	tobject = c.beginText(2*cm, 29.7*cm - 2*cm)

	try:
		for i in range(int(form["start"]),int(form["end"])+1,int(form["iterator"])):
			tobject.textLine(get(i))
		br=1
	except ValueError:
		pass

	if len(mo):
		for i in mo:
			tobject.textLine(get(i))
		br=1

	if br:
		c.drawText(tobject)
		c.showPage()
		c.save()
		num+=1
		return app.send_static_file(str(num)+".pdf")

	flash("Morate popuniti neko polje")
	return render_template("draw.html")

app.run()

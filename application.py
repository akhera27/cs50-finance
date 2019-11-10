import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_DOMAIN"]="https://aryan-cs50-finance.herokuapp.com"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

def ltdl(li):
    result=[]
    for l in li:
        result.append(list(l.values())[0])
    return result

@app.route("/",methods=["GET","POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    user=session["user_id"]
    if request.method == "POST":
        cash=float(request.form.get("cash"))
        if not cash or cash<1:
            return apology("Enter a valid amount")
        if cash>500000:
            return apology("Maximum limit of $500,000 reached")
        bal=ltdl(db.execute("SELECT cash FROM users WHERE id=:user",user=user))[0]
        db.execute("UPDATE users SET cash = :cash WHERE id = :user", cash=(cash+bal), user=user)
        redirect("/")
    balance={}
    stocks=[]
    symbol=db.execute("SELECT symbol FROM history GROUP BY symbol HAVING user_id=:user",user=user)
    # print(type(symbol),symbol)
    for s in symbol:
        stock={}
        stock["symbol"]=s["symbol"]
        stock["company"]=lookup(stock["symbol"])["name"]
        stock["currprice"]=round(lookup(stock["symbol"])["price"],4)
        stock["shares"]=db.execute("SELECT sum(shares) FROM history WHERE user_id=:user GROUP BY symbol HAVING symbol=:y",user=user,y=stock["symbol"])[0]["sum(shares)"]
        buy=ltdl(db.execute("SELECT mul FROM (SELECT user_id,price*shares as mul FROM history WHERE symbol=:y ORDER BY id) WHERE user_id=:user",user=user,y=stock["symbol"]))
        stock["prlo"]=0
        stock["total"]=round(sum([float(x) for x in buy]),4)
        stock["prlo"] = stock["currprice"] * stock["shares"]- stock["total"]
        stock["prlo"]=round(stock["prlo"],4)
        if stock["shares"] == 0:
            continue
        stocks.append(stock)

    balance["cash"]=round(ltdl(db.execute("SELECT cash FROM users WHERE id=:user",user=user))[0],4)
    balance["prlo"]=0
    balance["total"]=0
    for stock in stocks:
        balance["prlo"] += stock["prlo"]
        balance["total"] += stock["total"]
    balance["total"]=balance["cash"]+balance["total"]+balance["prlo"]

    return render_template("index.html",balance=balance,stocks=stocks)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        shares = request.form.get("shares")
        symbol = request.form.get("symbol").upper()
        if not shares or not symbol:
            return apology("Symbol not related to any company")
        try:
            shares = int(shares)
        except:
            return apology("Invalid no. of shares")
        print(f"shares:{shares}")
        print(f"shares:{type(shares)}")
        if shares<1:
            return apology("Enter a valid no. of shares")
        result = lookup(symbol)
        if result == None:
            return apology("Symbol not related to any company")
        user = session["user_id"]
        rows = db.execute("SELECT cash FROM users WHERE id = :user",user = user)
        cash = rows[0]
        cash=float(cash["cash"])
        cash = cash - (float(shares) * result["price"])
        if cash<0:
            return apology("Insufficient funds")
        db.execute("UPDATE users SET cash = :cash WHERE id = :user", cash=cash, user=user)
        db.execute("INSERT INTO history (user_id,symbol,shares,price) VALUES (:user, :symbol, :shares, :price)",user=user,symbol=symbol.upper(),shares=shares,price=result["price"])
        flash(f"{shares} shares of {symbol.upper()} bought")
        return redirect("/")

@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    user= request.args.get('username')
    if not user or len(user)<1:
        return jsonify(False)
    try:
        result=db.execute("SELECT id FROM users WHERE username=:user",user=user)
    except:
        return jsonify(False)
    if len(result)>0:
        return jsonify(True),200
    else:
        return jsonify(False)




@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    if request.method == "GET":
        result=db.execute("SELECT date,symbol,shares,price FROM history WHERE user_id=:user ORDER BY id DESC",user=session["user_id"])
        return render_template("history.html", result=result)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # print(f'In else {request.args.get("symbol")}')
    if request.method == "GET":
        return render_template("quote.html")

    else:

        argument= request.args.get("symbol")
        if argument=="":
            return apology("Symbol Not related to any company")
        if argument:
            result = lookup(request.args.get("symbol"))
            return jsonify(result)

        if not request.form.get("symbol"):
            return apology("Symbol Not related to any company")
        else:
            result = lookup(request.form.get("symbol").upper())
            if result == None:
                return apology("Symbol Not related to any company")
            else:
                return render_template("quoted.html",name=result["name"],price=result["price"],symbol=result["symbol"])



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        user=request.form.get("username")
        if not user:
            return apology("must provide username",400)
        password = request.form.get("password")
        confirmation=request.form.get("confirmation")
        rows = db.execute("SELECT * FROM users WHERE username= :username", username=user)
        if len(rows) > 0:
            return apology("username already exists")
        elif not confirmation or not password:
            return apology("must provide password",400)
        elif confirmation != password:
            return apology("password doesn't match",400)
        else:
            db.execute("INSERT INTO users (username,hash) VALUES(:username , :hash)", username=user, hash=generate_password_hash(password))
            rows=db.execute("SELECT * FROM users WHERE username=:username", username=user)
            session["user_id"]=rows[0]["id"]
            flash("Registered!")
            return redirect("/")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user = session["user_id"]
    if request.method == "GET":
        available=ltdl(db.execute("SELECT symbol FROM( SELECT symbol,sum(shares) as s FROM history WHERE user_id=:user GROUP BY symbol ORDER BY sum(shares) ASC) WHERE s>0",user=user))
        print(available)
        return render_template("sell.html",available=available)
    else:
        shares = request.form.get("shares")
        symbol = request.form.get("symbol")
        if not shares or not symbol:
            return apology("Symbol not related to any company")
        try:
            shares = int(shares)
        except:
            return apology("Invalid no. of shares")
        if shares<1:
            return apology("Invalid no. of shares")
        result = lookup(symbol)
        if result == None:
            return apology("Symbol not related to any company")
        try:
            available=db.execute("SELECT sum(shares) FROM history WHERE user_id=:user GROUP BY symbol HAVING symbol=:y",user=user,y=symbol.upper())[0]["sum(shares)"]
        except:
            print("Error")
            return apology("Insufficient no. of shares")
        if available < shares:
            return apology("Insufficient no. of shares")
        rows = db.execute("SELECT cash FROM users WHERE id = :user",user = user)[0]
        cash=float(rows["cash"])
        result=lookup(symbol)["price"]
        cash = cash + shares* result
        db.execute("UPDATE users SET cash = :cash WHERE id = :user", cash=cash, user=user)
        db.execute("INSERT INTO history (user_id,symbol,shares,price) VALUES (:user, :symbol, :shares, :price)",user=user,symbol=symbol.upper(),shares=-shares,price=result)
        flash(f"{shares} shares of {symbol.upper()} sold")
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

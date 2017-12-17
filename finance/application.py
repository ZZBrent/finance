from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
import datetime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

        cashList = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        cash = cashList[0]["cash"]
        totalValue = cash

        tableValues = list()

        amounts = db.execute("SELECT Amount FROM Transactions WHERE User_Id = :id", id = session["user_id"])
        symbols = db.execute("SELECT Stock_Symbol FROM Transactions WHERE User_Id = :id", id = session["user_id"])

        for x in range (0, len(amounts)):
            quote = lookup(symbols[x]['Stock_Symbol'])
            total = quote['price']*amounts[x]['Amount']
            stock = {'symbol': symbols[x]["Stock_Symbol"], 'amount': amounts[x]['Amount'], 'price': round(quote['price'], 2), 'total': total}
            valueFound = False
            for value in tableValues:
                if(value['symbol'] == stock['symbol']):
                    value['amount'] = value['amount'] + stock['amount']
                    totalValue = totalValue - value['total']
                    value['total'] = quote['price'] * value['amount']
                    totalValue = totalValue + value['total']
                    valueFound = True
                    break
            if valueFound != True:
                tableValues.append(stock)
                totalValue = stock['price'] * stock['amount'] + totalValue
            elif value['total'] == 0:
                tableValues.remove(stock)

        return render_template("index.html", stocks = tableValues, cash = round(cash, 2), total = round(totalValue, 2))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        if(request.form.get("symbol") == ""):
            return apology("Please enter a stock symbol.")
        elif(request.form.get("shares") == ""):
            return apology("Please enter a number of shares.")
        elif(0 >= int(request.form.get("shares"))):
            return apology("Shares must be greater than 0.")

        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Please enter a valid stock symbol.")

        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Share count must be an integer.")

        if(cash[0]['cash'] < quote['price']*shares):
            return apology(string.Format("You only have ${0}, so you can't spend ${1}.", cash[0]['cash'], quote['price']*shares))

        #Add new transaction to purchase history
        db.execute("INSERT INTO Transactions (User_Id, Time_Of_Transaction, Price, Amount, Stock_Symbol) VALUES(:id, :time, :price, :amount, :symbol)", id = session["user_id"], time = datetime.datetime.now(), price = quote['price'], amount = shares, symbol = quote['symbol'])
        db.execute("UPDATE users SET cash = cash - :total WHERE id = 1", total = quote['price']*shares)

        return render_template("stocksBought.html", name = quote['name'], amount = shares)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    tableValues = list()

    times = db.execute("SELECT Time_Of_Transaction FROM Transactions WHERE User_Id = :id", id = session["user_id"])
    prices = db.execute("SELECT Price FROM Transactions WHERE User_Id = :id", id = session["user_id"])
    amounts = db.execute("SELECT Amount FROM Transactions WHERE User_Id = :id", id = session["user_id"])
    symbols = db.execute("SELECT Stock_Symbol FROM Transactions WHERE User_Id = :id", id = session["user_id"])

    for x in range (0, len(amounts)):
            total = prices[x]['Price']*amounts[x]['Amount']*(-1)
            stock = {'date': times[x]['Time_Of_Transaction'], 'symbol': symbols[x]["Stock_Symbol"], 'amount': amounts[x]['Amount'], 'price': prices[x]['Price'], 'total': total}
            tableValues.append(stock)

    return render_template("history.html", stocks = tableValues)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if(request.form.get("symbol") == ""):
            return apology("Please enter a stock symbol.")

        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Please input a valid symbol")
        else:
            return render_template("quoteDisplay.html", name = quote['name'], price = quote['price'], symbol = quote['symbol'])
    else:
        return render_template("quote.html")

@app.route("/changePassword", methods=["GET", "POST"])
@login_required
def changePassword():
    """Change user's password."""
    if request.method == "POST":
        if(request.form.get("oldPassowrd") == ""):
            return apology("Please enter your old password.")
        elif(request.form.get("newPassword") == ""):
            return apology("Please enter a new password.")
        elif(request.form.get("passwordConfirmation") == ""):
            return apology("Please confirm your new password.")
        elif(request.form.get("passwordConfirmation") != request.form.get("newPassword")):
            return apology("Your password and password confirmation do not match.")

        hash = pwd_context.hash(request.form.get("newPassword"))

        rows = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

        # ensure username exists and password is correct
        if not pwd_context.verify(request.form.get("oldPassword"), rows[0]["hash"]):
            return apology("Your password is incorrect.")

        db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash = hash, id = session["user_id"])

        return redirect(url_for("passwordChanged"))
    else:
        return render_template("changePassword.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":
        if(request.form.get("username") == ""):
            return apology("Please enter a username.")
        elif(request.form.get("password") == ""):
            return apology("Please enter a password.")
        elif(request.form.get("passwordConfirmation") == ""):
            return apology("Please confirm your password.")
        elif(request.form.get("passwordConfirmation") != request.form.get("password")):
            return apology("Your password and password confirmation do not match.")

        hash = pwd_context.hash(request.form.get("password"))

        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=hash)
        if not result:
            return apology("Username already exists.  Please change it.")

            # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        session["user_id"] = rows[0]["id"]

        return redirect(url_for("index"))
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        if(request.form.get("symbol") == ""):
            return apology("Please enter a stock symbol.")
        elif(request.form.get("shares") == ""):
            return apology("Please enter a number of shares.")
        elif(0 >= int(request.form.get("shares"))):
            return apology("Shares must be greater than 0.")

        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Please enter a valid stock symbol.")

        amounts = db.execute("SELECT Amount FROM Transactions WHERE User_Id = :id AND Stock_Symbol = :symbol", id = session["user_id"], symbol = request.form.get("symbol"))

        if len(amounts) == 0:
            return apology("You don't have any shares of that stock to sell.")

        symbols = db.execute("SELECT Stock_Symbol FROM Transactions WHERE User_Id = :id AND Stock_Symbol = :symbol", id = session["user_id"], symbol = request.form.get("symbol"))

        totalAmount = 0

        for amount in amounts:
            totalAmount = totalAmount + amount['Amount']

        if(totalAmount < int(request.form.get("shares"))):
            return apology(string.Format("You only have {0} shares, so you can't sell {1}.", totalAmount, int(request.form.get("shares"))))

        #Make shares negative and check that they are integers
        try:
            shares = (-1)*int(request.form.get("shares"))
        except:
            return apology("Share count must be an integer.")

        #Add new transaction to purchase history
        db.execute("INSERT INTO Transactions (User_Id, Time_Of_Transaction, Price, Amount, Stock_Symbol) VALUES(:id, :time, :price, :amount, :symbol)", id = session["user_id"], time = datetime.datetime.now(), price = quote['price'], amount = shares, symbol = quote['symbol'])
        #Subtract total (since shares are negative, this will add to cash on hand)
        db.execute("UPDATE users SET cash = cash - :total WHERE id = :id", total = quote['price']*shares, id = session["user_id"])

        return render_template("stocksSold.html", name = quote['name'], amount = request.form.get("shares"))
    else:
        return render_template("sell.html")

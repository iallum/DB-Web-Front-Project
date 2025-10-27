
"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""
import os
# accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, session, flash
from datetime import datetime

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@34.139.8.30/proj1part2
#
# For example, if you had username ab1234 and password 123123, then the following line would be:
#
#     DATABASEURI = "postgresql://ab1234:123123@34.139.8.30/proj1part2"
#
# Modify these with your own credentials you received from TA!
DATABASE_USERNAME = "ita2121"
DATABASE_PASSWRD = "databases"
DATABASE_HOST = "34.139.8.30"
DATABASEURI = f"postgresql://ita2121:databases@34.139.8.30/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
# Example of running queries in your database
# Note that this will probably not work if you already have a table named 'test' in your database, containing meaningful data. This is only an example showing you how to run queries in your database using SQLAlchemy.
#
with engine.connect() as conn:
    create_table_command = """
    CREATE TABLE IF NOT EXISTS test (
        id serial,
        name text
    )
    """
    res = conn.execute(text(create_table_command))
    insert_table_command = """INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace')"""
    res = conn.execute(text(insert_table_command))
    # you need to commit for create, insert, update queries to reflect
    conn.commit()


@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request 
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request.

    The variable g is globally accessible.
    """
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't, the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to, for example, localhost:8111/foobar/ with POST or GET then you could use:
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: https://flask.palletsprojects.com/en/1.1.x/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#
@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect('/login')  # Force them to login
    
    # They're logged in, show the page
    email = session.get('email')
    
    '''
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data
    '''

    # DEBUG: this is debugging code to see what request looks like
    print(request.args)


    #
    # example of a database query
    #
    user_id = session.get('user_id')
    
    select_query = """SELECT u.name, e.event_name, e.location, e.date_time, i.accept_status 
                      FROM invite_guest i 
                      JOIN create_event c ON i.event_id = c.event_id 
                      JOIN "user" u ON u.user_id = c.user_id 
                      JOIN event e ON e.event_id = i.event_id 
                      WHERE i.user_id = :user_id
                      ORDER BY e.date_time"""
    
    params = {"user_id": user_id}
    cursor = g.conn.execute(text(select_query), params)
    
    upcoming_events = []
    past_events = []
    now = datetime.now()
    
    for result in cursor:
        event_date = result[3]
    
        formatted_date = event_date.strftime('%m/%d/%y at %I:%M %p')
        event = {
            'host': result[0],
            'event_name': result[1],
            'location': result[2],
            'date': formatted_date,
            'status': result[4]
        }
        if result[3] < now:
            past_events.append(event)
        else:
            upcoming_events.append(event)
    cursor.close()

    #
    # Flask uses Jinja templates, which is an extension to HTML where you can
    # pass data to a template and dynamically generate HTML based on the data
    # (you can think of it as simple PHP)
    # documentation: https://realpython.com/primer-on-jinja-templating/
    #
    # You can see an example template in templates/index.html
    #
    # context are the variables that are passed to the template.
    # for example, "data" key in the context variable defined below will be 
    # accessible as a variable in index.html:
    #
    #     # will print: [u'grace hopper', u'alan turing', u'ada lovelace']
    #     <div>{{data}}</div>
    #     
    #     # creates a <div> tag for each element in data
    #     # will print: 
    #     #
    #     #   <div>grace hopper</div>
    #     #   <div>alan turing</div>
    #     #   <div>ada lovelace</div>
    #     #
    #     {% for n in data %}
    #     <div>{{n}}</div>
    #     {% endfor %}
    #
    context = dict(
        upcoming_events=upcoming_events,
        past_events=past_events
    )
    
    #
    # render_template looks in the templates/ folder for files.
    # for example, the below file reads template/index.html
    #
    return render_template("index.html", **context)

#
# This is an example of a different path.  You can see it at:
# 
#     localhost:8111/another
#
# Notice that the function name is another() rather than index()
# The functions for each app.route need to have different names
#
@app.route('/another')
def another():
    return render_template("another.html")


# Example of adding new data to the database
@app.route('/add', methods=['POST'])
def add():
    # accessing form inputs from user
    name = request.form['name']
        # passing params in for each variable into query
    params = {}
    params["new_name"] = name
    g.conn.execute(text('INSERT INTO test(name) VALUES (:new_name)'), params)
    g.conn.commit()
    return redirect('/')


app.secret_key = 'simple-secret-key-for-class'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        query = 'SELECT email, name , user_id FROM "user" WHERE email = :email AND password = :password'
        params = {"email": email, "password": password}

        cursor = g.conn.execute(text(query), params)
        user = cursor.fetchone()
        cursor.close()

        if user:
            # Login successful
            session['email'] = user[0]
            session['name'] = user[1]
            session['user_id'] = user[2]
            session['logged_in'] = True
            return redirect('/')
        else:
            # Login failed
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

'''
@app.route('/login')
def login():
    abort(401)
    # Your IDE may highlight this as a problem - because no such function exists (intentionally).
    # This code is never executed because of abort().
    this_is_never_executed()
'''


##############################
from math import ceil
from sqlalchemy import text

@app.route('/recipes')
@app.route('/recipes')
def recipes():
    if not session.get('logged_in'):
        return redirect('/login')

    # pagination + search
    try:
        page = max(int(request.args.get('page', 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get('per_page', 12))
        if per_page < 1 or per_page > 50:
            per_page = 12
    except ValueError:
        per_page = 12

    q = (request.args.get('q') or '').strip()

    where = "WHERE r.title ILIKE :q" if q else ""
    params = {"limit": per_page, "offset": (page - 1) * per_page}
    if q:
        params["q"] = f"%{q}%"

    # keep it simple first; no ratings until list renders
    base_sql = f"""
      SELECT
        r.recipe_id,
        r.title,
        COALESCE(SUBSTRING(COALESCE(r.instructions, '') FOR 120), '') AS preview
      FROM recipe r
      {where}
      ORDER BY r.title ASC
      LIMIT :limit OFFSET :offset
    """
    count_sql = f"SELECT COUNT(*) FROM recipe r {where}"

    rows = g.conn.execute(text(base_sql), params).mappings().all()
    count = g.conn.execute(text(count_sql), params).scalar()
    has_more = (page * per_page) < count

    recipes = [
        {
            "recipe_id": r["recipe_id"],
            "title": r["title"],
            "preview": r["preview"],
            "avg_rating": None,  # add real avg later
        }
        for r in rows
    ]

    return render_template(
        "recipes.html",
        recipes=recipes,
        page=page,
        per_page=per_page,
        has_more=has_more,
        q=q,                 # ← make sure this is ONLY q=q
    )


@app.route('/recipes/<int:recipe_id>')
def recipe_detail(recipe_id):
    if not session.get('logged_in'):
        return redirect('/login')

    recipe_sql = """
      SELECT r.recipe_id,
             r.title,
             r.instructions,
             AVG(rv.rating)::float AS avg_rating
      FROM recipe r
      LEFT JOIN review rv ON rv.recipe_id = r.recipe_id
      WHERE r.recipe_id = :rid
      GROUP BY r.recipe_id, r.title, r.instructions
    """
    rec = g.conn.execute(text(recipe_sql), {"rid": recipe_id}).mappings().first()
    if not rec:
        abort(404)

    recipe = {
        "recipe_id": rec["recipe_id"],
        "title": rec["title"],
        "instructions": rec["instructions"],
        "avg_rating": rec["avg_rating"]
    }

    return render_template("recipe_detail.html", recipe=recipe)

##############################
if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using:

            python server.py

        Show the help text using:

            python server.py --help

        """

        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

run()

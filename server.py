
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
from math import ceil
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from flask import Flask, request, render_template, g, redirect, Response, abort, session, flash
from datetime import datetime

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

DATABASE_USERNAME = "ita2121"
DATABASE_PASSWRD = "databases"
DATABASE_HOST = "34.139.8.30"
DATABASEURI = f"postgresql://ita2121:databases@34.139.8.30/proj1part2"

engine = create_engine(DATABASEURI)

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

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect('/login')
    
    email = session.get('email')
    
    '''
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data
    '''

    print(request.args)
    
    user_id = session.get('user_id')
    
    select_query1 = """SELECT u.name, e.event_name, e.location, e.date_time, i.accept_status, e.event_id
                      FROM invite_guest i 
                      JOIN create_event c ON i.event_id = c.event_id 
                      JOIN "user" u ON u.user_id = c.user_id 
                      JOIN event e ON e.event_id = i.event_id 
                      WHERE i.user_id = :user_id
                      ORDER BY e.date_time"""
    
    params1 = {"user_id": user_id}
    invited_events = g.conn.execute(text(select_query1), params1)
    
    select_query2 = """SELECT u.name, e.event_name, e.location, e.date_time, TRUE, e.event_id
                      FROM create_event c
                      JOIN "user" u ON u.user_id = c.user_id 
                      JOIN event e ON e.event_id = c.event_id 
                      WHERE c.user_id = :user_id
                      ORDER BY e.date_time"""
    
    params2 = {"user_id": user_id}
    created_events = g.conn.execute(text(select_query2), params2)
    
    upcoming_events = []
    past_events = []
    now = datetime.now()
    
    for result in invited_events:
        event_date = result[3]
    
        formatted_date = event_date.strftime('%m/%d/%y at %I:%M %p')
        event = {
            'host': result[0],
            'event_name': result[1],
            'location': result[2],
            'date': formatted_date,
            'status': result[4],
            'event_id': result[5],
            'is_host': False
        }
        if result[3] < now:
            past_events.append(event)
        else:
            upcoming_events.append(event)
    invited_events.close()
    
    for result in created_events:
        event_date = result[3]
    
        formatted_date = event_date.strftime('%m/%d/%y at %I:%M %p')
        event = {
            'host': result[0],
            'event_name': result[1],
            'location': result[2],
            'date': formatted_date,
            'status': result[4],
            'event_id': result[5],
            'is_host': True
        }
        if result[3] < now:
            past_events.append(event)
        else:
            upcoming_events.append(event)
    invited_events.close()
    
    context = dict(
        upcoming_events=upcoming_events,
        past_events=past_events
    )

    return render_template("index.html", **context)

@app.route('/another')
def another():
    return render_template("another.html")

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
            session['email'] = user[0]
            session['name'] = user[1]
            session['user_id'] = user[2]
            session['logged_in'] = True
            return redirect('/')
        else:
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/recipes')
@app.route('/recipes')
def recipes():
    if not session.get('logged_in'):
        return redirect('/login')

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
            "avg_rating": None,  
        }
        for r in rows
    ]

    return render_template(
        "recipes.html",
        recipes=recipes,
        page=page,
        per_page=per_page,
        has_more=has_more,
        q=q,                 
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

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    if not session.get('logged_in'):
        return redirect('/login')
    
    user_id = session.get('user_id')
    
    # event dets
    event_query = """
        SELECT e.event_id, e.event_name, e.location, e.date_time, 
               u.name AS host_name, c.user_id AS host_id
        FROM event e
        JOIN create_event c ON e.event_id = c.event_id
        JOIN "user" u ON c.user_id = u.user_id
        WHERE e.event_id = :event_id
    """
    event_result = g.conn.execute(text(event_query), {"event_id": event_id}).fetchone()
    
    if not event_result:
        abort(404)
    
    event = {
        'event_id': event_result[0],
        'event_name': event_result[1],
        'location': event_result[2],
        'date_time': event_result[3].strftime('%m/%d/%y at %I:%M %p'),
        'date_time_html': event_result[3].strftime('%Y-%m-%dT%H:%M'),
        'host_name': event_result[4],
        'host_id': event_result[5]
    }
    
    now = datetime.now()
    is_past_event = event_result[3] < now
    is_host = (event_result[5] == user_id)
    
    # invited guests + accept status
    guests_query = """
        SELECT u.user_id, u.name, i.accept_status
        FROM invite_guest i
        JOIN "user" u ON i.user_id = u.user_id
        WHERE i.event_id = :event_id
        ORDER BY 
            CASE 
                WHEN i.accept_status = TRUE THEN 1
                WHEN i.accept_status = FALSE THEN 2
                WHEN i.accept_status IS NULL THEN 3
                ELSE 4
            END,
            u.name
    """
    guests_result = g.conn.execute(text(guests_query), {"event_id": event_id})
    
    confirmed = []
    declined = []
    pending = []
    
    for guest in guests_result:
        guest_info = {
            'user_id': guest[0],
            'name': guest[1]
        }
        if guest[2] is True:
            confirmed.append(guest_info)
        elif guest[2] is False:
            declined.append(guest_info)
        else:
            pending.append(guest_info)
    
    guests_result.close()
    
    # recipes
    recipes_query = """
        SELECT r.recipe_id, r.title AS added_by
        FROM plan_meal p
        JOIN recipe r ON r.recipe_id = p.recipe_id
        WHERE p.event_id = :event_id
        ORDER BY r.title ASC
    """
    recipes_result = g.conn.execute(text(recipes_query), {"event_id": event_id})
    recipes = []
    for recipe in recipes_result:
        recipes.append({
            'recipe_id': recipe[0],
            'title': recipe[1]
        })
    recipes_result.close()
    
    # comments
    comments_query = """
        SELECT c.comment_id, u.name, c.date_time, c.text, c.user_id
        FROM comment c
        JOIN has_comment h on h.comment_id = c.comment_id
        JOIN "user" u ON c.user_id = u.user_id
        WHERE h.event_id = :event_id
        ORDER BY c.date_time DESC
    """
    comments_result = g.conn.execute(text(comments_query), {"event_id": event_id})
    comments = []
    for comment in comments_result:
        comments.append({
            'comment_id': comment[0],
            'author': comment[1],
            'date_time': comment[2].strftime('%m/%d/%y at %I:%M %p'),
            'text': comment[3],
            'author_id': comment[4]
        })
    comments_result.close()
    
    context = {
        'event': event,
        'confirmed': confirmed,
        'declined': declined,
        'pending': pending,
        'recipes': recipes,
        'comments': comments,
        'is_past_event': is_past_event,
        'is_host': is_host
    }
    
    return render_template('event_details.html', **context)

@app.route('/event/<int:event_id>/update_status', methods=['POST'])
def update_attendance(event_id):
    if not session.get('logged_in'):
        return redirect('/login')
    
    user_id = session.get('user_id')
    status = request.form.get('status')
    
    if status == 'yes':
        accept_status = True
    elif status == 'no':
        accept_status = False
    else:
        accept_status = None
    
    update_query = """
        UPDATE invite_guest 
        SET accept_status = :status 
        WHERE event_id = :event_id AND user_id = :user_id
    """
    
    g.conn.execute(text(update_query), {
        "status": accept_status,
        "event_id": event_id,
        "user_id": user_id
    })
    g.conn.commit()
    
    return redirect(f'/event/{event_id}')

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if not session.get('logged_in'):
        return redirect('/login')

    if request.method == 'POST':
        event_name = request.form.get('event_name')
        location = request.form.get('location')
        user_id = session.get('user_id')
        month = request.form.get('month')
        day = request.form.get('day')
        year = request.form.get('year')
        hour = request.form.get('hour')
        minute = request.form.get('minute')
        ampm = request.form.get('ampm')

        if not all([event_name, location, month, day, year, hour, minute, ampm]):
            flash('Please fill in all fields!', 'error')
            return redirect('/create_event')

        date_time_combined_str = f"{month}/{day}/{year} {hour}:{minute} {ampm}"
        DATE_TIME_INPUT_FORMAT = '%m/%d/%Y %I:%M %p' 
        DB_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

        try:
            event_datetime_obj = datetime.strptime(date_time_combined_str, DATE_TIME_INPUT_FORMAT)
            if event_datetime_obj <= datetime.now():
                flash('Event date cannot have already passed.', 'error')
                return redirect('/create_event')
            event_datetime_formatted = event_datetime_obj.strftime(DB_DATETIME_FORMAT)
        except ValueError:
            flash('Invalid date and/or time entered. Please enter using numeric values (ex., 01/01/2025 09:30 PM).', 'error')
            return redirect('/create_event')

        try:
            with g.conn.begin():
                insert_event_query = """
                    INSERT INTO event (event_name, location, date_time) 
                    VALUES (:event_name, :location, :date_time)
                    RETURNING event_id
                """
                event_id_result = g.conn.execute(
                    text(insert_event_query), 
                    {"event_name": event_name, "location": location, "date_time": event_datetime_formatted} 
                ).fetchone()
                
                event_id = event_id_result[0]

                insert_create_event_query = """
                    INSERT INTO create_event (event_id, user_id) 
                    VALUES (:event_id, :user_id)
                """
                g.conn.execute(
                    text(insert_create_event_query), 
                    {"event_id": event_id, "user_id": user_id}
                )
                
            return redirect('/') 
            
        except Exception as e:
            print(f"Database error during event creation: {e}")
            flash('Ae database error occurred while creating the event.', 'error')
            return redirect('/create_event')

    return render_template('create_event.html')

@app.route('/event/<int:event_id>/invite', methods=['POST'])
def invite_guest(event_id):
    if not session.get('logged_in'):
        return redirect('/login')

    host_id = session.get('user_id')
    guest_email = request.form.get('guest_email', '').strip()

    guest_query = 'SELECT user_id FROM "user" WHERE email = :email'
    guest_result = g.conn.execute(text(guest_query), {"email": guest_email}).fetchone()
    
    if not guest_result:
        flash(f"No user found with that email. Guests must be registered app users.", 'error')
        return redirect(f'/event/{event_id}')
    guest_user_id = guest_result[0]

    if guest_user_id == host_id:
        flash("You cannot invite yourself.", 'error')
        return redirect(f'/event/{event_id}')

    check_invited_query = "SELECT 1 FROM invite_guest WHERE event_id = :event_id AND user_id = :user_id"
    already_invited = g.conn.execute(text(check_invited_query), {"event_id": event_id, "user_id": guest_user_id}).fetchone()

    if already_invited:
        flash(f"User has already invited to this event.", 'error')
        return redirect(f'/event/{event_id}')

    try:
        invite_query = """
            INSERT INTO invite_guest (event_id, user_id, accept_status) 
            VALUES (:event_id, :user_id, NULL)
        """
        g.conn.execute(text(invite_query), {
            "event_id": event_id, 
            "user_id": guest_user_id
        })
        g.conn.commit()

    except Exception as e:
        print(f"Error inviting guest: {e}")
        flash('An internal database error occurred while inviting the guest.', 'error')

    return redirect(f'/event/{event_id}')

@app.route('/event/<int:event_id>/uninvite_guests', methods=['POST'])
def uninvite_guests(event_id):
    if not session.get('logged_in'):
        return redirect('/login')

    host_id = session.get('user_id')
    users_to_uninvite = request.form.getlist('user_id_to_uninvite')

    if not users_to_uninvite:
        flash("No guests were selected to uninvite.", 'error')
        return redirect(f'/event/{event_id}')

    try:
        uninvited = ', '.join([f":id_{i}" for i in range(len(users_to_uninvite))])
        params = {f"id_{i}": int(user_id) for i, user_id in enumerate(users_to_uninvite)}
        params['event_id'] = event_id
        
        delete_query = f"""
            DELETE FROM invite_guest 
            WHERE event_id = :event_id AND user_id IN ({uninvited})
        """
        
        result = g.conn.execute(text(delete_query), params)
        g.conn.commit()
            
    except Exception as e:
        print(f"Error uninviting guests: {e}")
        flash('An internal database error occurred while uninviting guests.', 'error')

    return redirect(f'/event/{event_id}')

@app.route('/event/<int:event_id>/edit_details', methods=['POST'])
def edit_event_details(event_id):
    if not session.get('logged_in'):
        return redirect('/login')

    new_name = request.form.get('event_name')
    new_location = request.form.get('location')
    new_date_time_str = request.form.get('date_time') # Simple text string
    
    try:
        DATE_FORMAT = '%m/%d/%y at %I:%M %p'
                
        new_date_time_obj = datetime.strptime(new_date_time_str, DATE_FORMAT)
        
        update_query = """
            UPDATE event 
            SET 
                event_name = :event_name, 
                location = :location, 
                date_time = :date_time 
            WHERE event_id = :event_id
        """
        
        g.conn.execute(text(update_query), {
            "event_name": new_name,
            "location": new_location,
            "date_time": new_date_time_obj,
            "event_id": event_id
        })
        g.conn.commit()
            
    except ValueError:
        flash(f"Error: Date-time format must be {DATE_FORMAT}.", 'error')
    except Exception as e:
        print(f"Error updating event details: {e}")
        flash('An error occurred while attempting to save changes.', 'error')

    return redirect(f'/event/{event_id}')

@app.route('/event/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    if not session.get('logged_in'):
        return redirect('/login')

    try:
        with g.conn.begin():
            g.conn.execute(text("DELETE FROM invite_guest WHERE event_id = :event_id"), {"event_id": event_id})
            g.conn.execute(text("DELETE FROM create_event WHERE event_id = :event_id"), {"event_id": event_id})
            g.conn.execute(text("DELETE FROM plan_meal WHERE event_id = :event_id"), {"event_id": event_id})
            g.conn.execute(text("DELETE FROM write_comment WHERE comment_id IN (SELECT comment_id FROM has_comment WHERE event_id = :event_id)"), {"event_id": event_id})
            g.conn.execute(text("DELETE FROM comment WHERE comment_id IN (SELECT comment_id FROM has_comment WHERE event_id = :event_id)"), {"event_id": event_id})
            g.conn.execute(text("DELETE FROM has_comment WHERE event_id = :event_id"), {"event_id": event_id})
            g.conn.execute(text("DELETE FROM event WHERE event_id = :event_id"), {"event_id": event_id})
        return redirect('/')

    except Exception as e:
        print(f"Database error during event deletion: {e}")
        flash('An error occurred while attempting to delete the event.', 'error')
        return redirect(f'/event/{event_id}')

@app.route('/event/<int:event_id>/comment/add', methods=['POST'])
def add_comment(event_id):
    if not session.get('logged_in'):
        return redirect('/login')

    user_id = session.get('user_id')
    comment_text = request.form.get('comment_text', '').strip()
    
    if not comment_text:
        flash("Comment cannot be empty.", 'error')
        return redirect(f'/event/{event_id}')

    try:
        with g.conn.begin():
            insert_comment_query = """
                INSERT INTO comment (user_id, date_time, text) 
                VALUES (:user_id, NOW(), :text)
                RETURNING comment_id
            """
            comment_result = g.conn.execute(text(insert_comment_query), {
                "user_id": user_id,
                "text": comment_text
            }).fetchone()
            
            new_comment_id = comment_result[0]

            insert_write_query = """
                INSERT INTO write_comment (user_id, comment_id)
                VALUES (:user_id, :comment_id)
            """
            g.conn.execute(text(insert_write_query), {
                "user_id": user_id,
                "comment_id": new_comment_id
            })
            
            insert_has_query = """
                INSERT INTO has_comment (event_id, comment_id)
                VALUES (:event_id, :comment_id)
            """
            g.conn.execute(text(insert_has_query), {
                "event_id": event_id,
                "comment_id": new_comment_id
            })

    except Exception as e:
        print(f"Error adding comment: {e}")
        flash('An internal database error occurred while adding the comment.', 'error')

    return redirect(f'/event/{event_id}')

@app.route('/event/<int:event_id>/comment/<int:comment_id>/edit', methods=['POST'])
def edit_comment(event_id, comment_id):
    if not session.get('logged_in'):
        return redirect('/login')

    user_id = session.get('user_id')
    new_text = request.form.get('edited_comment_text', '').strip()
    
    if not new_text:
        flash("Comment cannot be empty.", 'error')
        return redirect(f'/event/{event_id}')

    try:
        update_query = """
            UPDATE comment 
            SET text = :new_text, date_time = NOW()
            WHERE comment_id = :comment_id
        """
        g.conn.execute(text(update_query), {
            "new_text": new_text,
            "comment_id": comment_id
        })
        g.conn.commit()

    except Exception as e:
        print(f"Error editing comment: {e}")
        flash('An internal database error occurred while editing the comment.', 'error')

    return redirect(f'/event/{event_id}')

@app.route('/event/<int:event_id>/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(event_id, comment_id):
    if not session.get('logged_in'):
        return redirect('/login')

    user_id = session.get('user_id')

    try:
        with g.conn.begin():
            g.conn.execute(text("DELETE FROM write_comment WHERE comment_id = :comment_id"), {"comment_id": comment_id})
            g.conn.execute(text("DELETE FROM has_comment WHERE comment_id = :comment_id"), {"comment_id": comment_id})
            g.conn.execute(text("DELETE FROM comment WHERE comment_id = :comment_id"), {"comment_id": comment_id})
        
    except Exception as e:
        print(f"Error deleting comment: {e}")
        flash('An internal database error occurred while deleting the comment.', 'error')

    return redirect(f'/event/{event_id}')

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

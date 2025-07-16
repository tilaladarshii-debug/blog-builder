from flask import Flask, render_template, request, redirect, session, url_for, flash
from db import connect_to_db
import os
from werkzeug.utils import secure_filename
from config import DATABASE_CONFIG, UPLOAD_FOLDER, SECRET_KEY
from datetime import datetime
from flask_login import current_user

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Connect to database
def get_connection():
    return connect_to_db(**DATABASE_CONFIG)

try:
    connection = get_connection()
    cursor = connection.cursor()
    print("Database connected.")
except Exception as e:
    print("Database connection failed:", e)

# Home
@app.route('/')
def home():
    page = int(request.args.get('page', 1))
    limit = 6
    offset = (page - 1) * limit
    connection = get_connection()
    cur = connection.cursor()
    cur.execute("SELECT posts.id, posts.title, posts.image, posts.created_at, users.username FROM posts JOIN users ON posts.user_id = users.id ORDER BY posts.created_at DESC LIMIT %s OFFSET %s", (limit + 1, offset))
    rows = cur.fetchall()
    cur.close()
    connection.close()
    has_more = len(rows) > limit
    posts = rows[:limit]
    return render_template("home.html", posts=[{'id': r[0], 'title': r[1], 'image': r[2], 'created_at': r[3], 'username': r[4],} for r in posts], has_more=has_more, next_page=page + 1, page=page)

#like
@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')
    connection = get_connection()
    cur = connection.cursor()
    cur.execute("SELECT user_id FROM posts WHERE id = %s", (post_id,))
    owner = cur.fetchone()
    if owner and owner[0] == user_id:
        return redirect(url_for('view_post', post_id=post_id))
    # Check if the user already liked the post
    cur.execute("SELECT * FROM likes WHERE user_id = %s AND post_id = %s", (user_id, post_id))
    already_liked = cur.fetchone()
    if already_liked:
        # Unlike
        cur.execute("DELETE FROM likes WHERE user_id = %s AND post_id = %s", (user_id, post_id))
    else:
        # Like
        cur.execute("INSERT INTO likes (user_id, post_id) VALUES (%s, %s)", (user_id, post_id))
    connection.commit()
    cur.close()
    connection.close()
    return redirect(url_for('view_post', post_id=post_id))

# view post
@app.route('/post/<int:post_id>')
def view_post(post_id):
    connection = get_connection()
    cur = connection.cursor()

        # 1. Fetch the post
    cur.execute("SELECT posts.*, users.username, posts.created_at FROM posts JOIN users ON posts.user_id = users.id WHERE posts.id = %s", (post_id,))
    post = cur.fetchone()
    if not post:
        cur.close()
        connection.close()
        return redirect('/')  # post not found

        # 2. Fetch comments
    cur.execute("SELECT c.comment_text, u.username, c.created_at FROM comments c JOIN users u ON c.user_id = u.id WHERE c.post_id = %s ORDER BY c.created_at DESC ", (post_id,))
    comment_rows = cur.fetchall()
    comments = [
        {"text": row[0], "username": row[1], "created_at": row[2]}
        for row in comment_rows
    ]
          
        # 3. Fetch like count
    cur.execute("SELECT COUNT(*) FROM likes WHERE post_id = %s", (post_id,))
    like_count = cur.fetchone()[0]

        # 4. Like logic
    user_id = session.get('user_id')
    is_logged_in = 'user_id' in session
    is_liked = False
    can_like = False
    if user_id:
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        if result:
            username = result[0]
            cur.execute("SELECT 1 FROM likes WHERE user_id = %s AND post_id = %s", (user_id, post_id))
            is_liked = cur.fetchone() is not None
            can_like = username != post[4]
    cur.close()
    connection.close()
    is_owner = (session.get('username') == post[-1])

    return render_template("view_post.html", post=post, post_id=post_id, comments = comments, like_count=like_count, is_liked=is_liked, can_like=can_like, is_owner=is_owner,
    is_logged_in=('user_id' in session))
    
# comment count
@app.route("/post/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    if request.method == 'POST':
        comment_text = request.form["comment"]
        user_id = session.get("user_id")
        connection = get_connection()
        cur = connection.cursor()
        cur.execute("INSERT INTO comments (post_id, user_id, comment_text) VALUES (%s, %s, %s)", (post_id, user_id, comment_text))
        cur.execute("UPDATE posts SET comment_count = comment_count + 1 WHERE id = %s", (post_id,))
        connection.commit()
        cur.close()
        connection.close()
        return redirect("view_post.html")
    return render_template('home.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        connection = get_connection()
        cur = connection.cursor()
        cur.execute("SELECT id, username FROM users WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()
        connection.commit()
        connection.close()
        if user:
            session['user_id'], session['username'] = user
            return redirect('/dashboard')
        else:
            flash("Invalid credentials")
    return render_template('login.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        pwd = request.form['password']
        connection = get_connection()
        cur = connection.cursor()
        cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, pwd))
        connection.commit()
        connection.close()
        flash("Registration successful. Please log in.")
        return redirect('/login')
    return render_template('register.html')

# Dashboard
@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')
    connection = get_connection() 
    cur = connection.cursor()
    
    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    username_result = cur.fetchone()
    username = username_result[0] if username_result else "User"
    
    cur.execute("SELECT id, title, image, created_at FROM posts WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    rows = cur.fetchall()

    formatted_posts = []
    for row in rows:
        formatted_posts.append({
        'id': row[0],
        'title': row[1],
        'image': row[2],
        'created_at': row[3].strftime("%d %B %Y, %I:%M %p")
    })

    cur.close()
    connection.close()
    return render_template("dashboard.html", username = username, posts = formatted_posts)

# Add Post
@app.route('/add', methods=['GET', 'POST'])
def add_post():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        status = request.form['status']
        schedule_time = request.form.get('schedule_time')
        user_id = session.get('user_id')
        
        image_file = request.files.getlist('image[]')[0] if request.files.getlist('image[]') else None

        if image_file and image_file.filename != '':
            image = secure_filename(image_file.filename)
            image_path = os.path.join('static/uploads', image)
            image_file.save(image_path)
                    
        if status == 'publish':
            status = 'published'
            schedule_time = None
        elif status == 'draft':
            status = 'draft'
            schedule_time = None
        else: 
            status = 'scheduled'
            schedule_time = schedule_time
        connection = get_connection()
        cur = connection.cursor()
        cur.execute("INSERT INTO posts (title, content, image, status, schedule_time, user_id) VALUES (%s, %s, %s, %s, %s, %s) ", (title, content, image, status, schedule_time, user_id))
        connection.commit()
        cur.close()
        connection.close()
        flash('Post added successfully!')
        return redirect('/dashboard')
    return render_template('add_post.html')

# Edit Post
@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')
    connection = get_connection()
    cur = connection.cursor()

    # Fetch the post first (for both GET and POST)
    cur.execute("SELECT title, content, image FROM posts WHERE id = %s", (post_id,))
    post = cur.fetchone()

    if not post:
        flash("Post not found.")
        return redirect('/dashboard')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image_file = request.files.get('image[]')
        image_filename = post[2]

        # Replace image if a new one is uploaded
        if image_file and image_file.filename != '':
            if post[2]:
                old_path = os.path.join(UPLOAD_FOLDER, post[2])
                if os.path.exists(old_path):
                    os.remove(old_path)
                    
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join('static/uploads', filename))
            image_filename = filename

        cur.execute("UPDATE posts SET title=%s, content=%s, image=%s WHERE id=%s", (title, content, image_filename, post_id))
        connection.commit()
        cur.close()
        connection.close()
        flash("Post updated successfully!")
        return redirect('/dashboard')

    # Pass the existing post data to the form
    return render_template('edit_post.html', post=post)


# Delete Post
@app.route('/delete/<int:id>')
def delete_post(id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')
    connection = get_connection()
    cur = connection.cursor()
    cur.execute("DELETE FROM posts WHERE id=%s", (id,))
    connection.commit()
    connection.close()
    return redirect('/dashboard')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True, use_reloader=False)

import socket
import threading
import sqlite3
import datetime

DB_FILE = 'bbs.db'
LOG_FILE = 'log.txt'
online_users = 0
unread_messages = 0

def log_activity(message):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{current_time}] {message}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as log_file:
        log_file.write(log_entry)

def create_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            full_name TEXT NOT NULL,
            bbs_number TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AddressBook (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS PrivateMessages (
            id INTEGER PRIMARY KEY,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ForumMessages (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            post_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

create_database()

def register_user(username, password, email, full_name, bbs_number=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO Users (username, password, email, full_name, bbs_number)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, password, email, full_name, bbs_number))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT password FROM Users WHERE username=?', (username,))
    row = cursor.fetchone()

    if row is not None and row[0] == password:
        conn.close()
        return True
    else:
        conn.close()
        return False

def update_address_book(name, address):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('INSERT OR REPLACE INTO AddressBook (name, address) VALUES (?, ?)', (name, address))
    conn.commit()
    conn.close()

def delete_from_address_book(name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM AddressBook WHERE name = ?', (name,))
    conn.commit()
    conn.close()

def get_address_book():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT name, address FROM AddressBook')
    entries = cursor.fetchall()
    conn.close()

    return entries

def create_message_table():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS PrivateMessages (
            id INTEGER PRIMARY KEY,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

create_message_table()

def get_private_messages(username):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT id, sender, recipient, message FROM PrivateMessages WHERE recipient = ?', (username,))
    messages_received = cursor.fetchall()
    
    conn.close()

    return messages_received

def send_private_message(sender, recipient, message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('INSERT INTO PrivateMessages (sender, recipient, message) VALUES (?, ?, ?)',
                   (sender, recipient, message))
    conn.commit()
    conn.close()

def view_registered_users(client_socket):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT username FROM Users')
    users = cursor.fetchall()
    conn.close()

    if not users:
        client_socket.send(b"\r\nNo registered users.\r\n")
    else:
        client_socket.send(b"\r\nRegistered Users:\r\n")
        user_list = [user[0] for user in users]
        user_list_str = "\r\n".join(user_list).encode('utf-8')
        client_socket.send(user_list_str + b"\r\n")

def read_characters(client_socket):
    data = ''
    while True:
        char = client_socket.recv(1)
        if not char or char == b'\n':
            break
        try:
            char_utf8 = char.decode('utf-8')
            data += char_utf8
            client_socket.send(char)  # Send the character back to the client
        except UnicodeDecodeError:
            char_fallback = char.decode('latin-1')
            data += char_fallback
            client_socket.send(char)  # Send the character back to the client

    return data

def show_address_book(client_socket):
    entries = get_address_book()
    if not entries:
        client_socket.send(b"\r\nThe address book is empty.\r\n")
    else:
        client_socket.send(b"\r\nAddress Book:\r\n")
        for name, address in entries:
            client_socket.send(f"{name}: {address}\r\n".encode('utf-8'))

def inbox(client_socket, username):
    messages_received = get_private_messages(username)
    client_socket.send("\r\nInbox:\r\n".encode('utf-8'))
    client_socket.send(b"\r\nReceived Messages:\r\n")
    if messages_received:
        for message_id, sender, _, message in messages_received:
            client_socket.send(f"ID: {message_id}, From {sender}: {message}\r\n".encode('utf-8'))
    else:
        client_socket.send(b"No received messages.\r\n")

def send_message_menu(client_socket, authenticated_user):
    client_socket.send(b"\r\nEnter the recipient's username: ")
    recipient = read_characters(client_socket)
    client_socket.send(b"\r\nEnter your message: ")
    message = read_characters(client_socket)

    formatted_message = f"{authenticated_user} {recipient.strip()} {message.strip()}"
    log_activity(f"{authenticated_user} sent a message to {recipient.strip()}: {message.strip()}")

    send_private_message(authenticated_user, recipient.strip(), formatted_message)
    client_socket.send(b"\r\nMessage sent successfully.\r\n")

def view_profile(client_socket, authenticated_user):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM Users WHERE username=?', (authenticated_user,))
    user_profile = cursor.fetchone()
    conn.close()

    if user_profile:
        client_socket.send(b"\r\nUser Profile:\r\n")
        client_socket.send(f"Username: {user_profile[1]}\r\n".encode('utf-8'))
        client_socket.send(f"Email: {user_profile[3]}\r\n".encode('utf-8'))
        client_socket.send(f"Full Name: {user_profile[4]}\r\n".encode('utf-8'))            

def create_forum_table():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ForumMessages (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            post_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

create_forum_table()

def get_forum_messages():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT id, subject FROM ForumMessages ORDER BY id DESC')
    messages = cursor.fetchall()
    conn.close()

    return messages

def post_forum_message(username, subject, message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('INSERT INTO ForumMessages (username, subject, message) VALUES (?, ?, ?)',
                   (username, subject, message))
    conn.commit()
    conn.close()

def handle_client(client_socket):
    global online_users
    global unread_messages

    authenticated_user = register_client(client_socket)
    if authenticated_user:
        online_users += 1

    main_menu = (
        f"\r\nOnline Users: {online_users}\r\n"
        f"Unread Messages: {unread_messages}\r\n"
        "\r\n1. View Address Book\r\n2. View Registered Users\r\n3. View Profile\r\n4. Forum\r\n5. Logout\r\n\r\nEnter your choice: "
    )

    profile_menu = (
    b"\r\n1. Inbox\r\n2. Show User Details\r\n3. Go Back to Main Menu\r\n4. Logout\r\nEnter your choice: "
)

    address_book_menu = (
        b"\r\n1. Show Address Book\r\n2. Add BBS to Address Book\r\n3. Delete from Address Book\r\n4. Back to Profile Menu\r\nEnter your choice: "
    )

    registered_users_submenu = (
        b"\r\n1. Show Registered Users\r\n2. Send a Message\r\n3. Back to Main Menu\r\nEnter your choice: "
    )

    while True:
        try:
            if not authenticated_user:
                return

            if authenticated_user:
                client_socket.send(main_menu.encode('utf-8'))
                choice = read_characters(client_socket)

                if choice.strip() == '1':
                    while True:
                        client_socket.send(address_book_menu)
                        sub_choice = read_characters(client_socket)

                        if sub_choice.strip() == '1':
                            show_address_book(client_socket)
                            client_socket.send(b"\r\n4. Back to Address Book Menu\r\n")
                        elif sub_choice.strip() == '2':
                            client_socket.send(b"\r\nEnter BBS name: ")
                            bbs_name = read_characters(client_socket)
                            client_socket.send(b"\r\nEnter BBS address: ")
                            bbs_address = read_characters(client_socket)

                            if update_address_book(bbs_name, bbs_address):
                                client_socket.send(b"\r\nBBS added to Address Book.\r\n")
                                log_activity(f"{authenticated_user} added BBS '{bbs_name}' to Address Book.")
                            else:
                                client_socket.send(b"\r\nBBS with the same name already exists in the Address Book.\r\n")
                        elif sub_choice.strip() == '3':
                            client_socket.send(b"\r\nEnter the name to delete: ")
                            name_to_delete = read_characters(client_socket)
                            delete_from_address_book(name_to_delete)
                            client_socket.send(b"\r\nEntry deleted from Address Book.\r\n")
                            log_activity(f"{authenticated_user} deleted entry '{name_to_delete}' from Address Book.")
                        elif sub_choice.strip() == '4':
                            break
                        else:
                            client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")

                elif choice.strip() == '2':
                    while True:
                        client_socket.send(registered_users_submenu)
                        sub_choice = read_characters(client_socket)

                        if sub_choice.strip() == '1':
                            view_registered_users(client_socket)
                        elif sub_choice.strip() == '2':
                            send_message_menu(client_socket, authenticated_user)
                        elif sub_choice.strip() == '3':
                            break
                        else:
                            client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")

                elif choice.strip() == '3':
                    while True:
                        client_socket.send(profile_menu)
                        profile_choice = read_characters(client_socket)

                        if profile_choice.strip() == '1':
                            inbox(client_socket, authenticated_user)
                        elif profile_choice.strip() == '2':
                            client_socket.send(b"\r\nUser Details:\r\n")
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute('SELECT username, email, full_name, bbs_number FROM Users WHERE username = ?', (authenticated_user,))
                            user_details = cursor.fetchone()
                            conn.close()
                            if user_details:
                                username, email, full_name, bbs_number = user_details
                                client_socket.send(f"Username: {username}\r\n".encode('utf-8'))
                                client_socket.send(f"Email: {email}\r\n".encode('utf-8'))
                                client_socket.send(f"Full Name: {full_name}\r\n".encode('utf-8'))
                                if bbs_number:
                                    client_socket.send(f"BBS Number: {bbs_number}\r\n".encode('utf-8'))
                            client_socket.send(b"\r\n")
                        elif profile_choice.strip() == '3':
                            break
                        elif profile_choice.strip() == '4':
                            client_socket.send(b"\r\nLogging out...\r\n")
                            log_activity(f"{authenticated_user} logged out.")
                            break
                        else:
                            client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")

                elif choice.strip() == '4':
                    while True:
                        client_socket.send(b"\r\nForum:\r\n")
                        client_socket.send(b"\r\n1. View Forum Topics\r\n2. Post a New Topic\r\n3. Back to Main Menu\r\nEnter your choice: ")
                        forum_choice = read_characters(client_socket)

                        if forum_choice.strip() == '1':
                            client_socket.send(b"\r\nForum Topics:\r\n")
                            forum_messages = get_forum_messages()
                            if forum_messages:
                                for index, (message_id, subject) in enumerate(forum_messages, start=1):
                                    client_socket.send(f"{index}. {subject}\r\n".encode('utf-8'))
                                client_socket.send(b"\r\n")
                                client_socket.send(b"\r\nEnter the topic number to view or '0' to go back: ")
                                topic_choice = read_characters(client_socket)
                                topic_choice = topic_choice.strip()
                                if topic_choice.isdigit():
                                    topic_choice = int(topic_choice)
                                    if 1 <= topic_choice <= len(forum_messages):
                                        message_id = forum_messages[topic_choice - 1][0]
                                        view_forum_message(client_socket, message_id)
                                    elif topic_choice == 0:
                                        continue
                                    else:
                                        client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")
                                else:
                                    client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")
                            else:
                                client_socket.send(b"\r\nNo topics available.\r\n")
                        elif forum_choice.strip() == '2':
                            client_socket.send(b"\r\nEnter the subject: ")
                            subject = read_characters(client_socket)
                            client_socket.send(b"\r\nEnter your message: ")
                            message = read_characters(client_socket)
                            post_forum_message(authenticated_user, subject.strip(), message.strip())
                            client_socket.send(b"\r\nTopic posted successfully.\r\n")
                        elif forum_choice.strip() == '3':
                            break
                        else:
                            client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")

                elif choice.strip() == '5':
                    client_socket.send(b"\r\nLogging out...\r\n")
                    log_activity(f"{authenticated_user} logged out.")
                    break
                else:
                    client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")
        except Exception as e:
            log_activity(f"Error: {str(e)}")
            break

def view_forum_message(client_socket, message_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT username, subject, message, post_date FROM ForumMessages WHERE id = ?', (message_id,))
    message_data = cursor.fetchone()
    conn.close()

    if message_data:
        username, subject, message, post_date = message_data
        client_socket.send(b"\r\nForum Message:\r\n")
        client_socket.send(f"Username: {username}\r\n".encode('utf-8'))
        client_socket.send(f"Subject: {subject}\r\n".encode('utf-8'))
        client_socket.send(f"Date: {post_date}\r\n".encode('utf-8'))
        client_socket.send(f"Message:\r\n{message}\r\n".encode('utf-8'))
    else:
        client_socket.send(b"\r\nForum message not found.\r\n")

def register_client(client_socket):
    client_socket.send(b"\r\nWelcome to the Bulletin Board System!\r\n")
    while True:
        client_socket.send(b"\r\n1. Register\r\n2. Login\r\n3. Quit\r\nEnter your choice: ")
        choice = read_characters(client_socket)

        if choice.strip() == '1':
            client_socket.send(b"\r\nRegistration:\r\n")
            client_socket.send(b"\r\nEnter a username: ")
            username = read_characters(client_socket)
            client_socket.send(b"\r\nEnter a password: ")
            password = read_characters(client_socket)
            client_socket.send(b"\r\nEnter your email: ")
            email = read_characters(client_socket)
            client_socket.send(b"\r\nEnter your full name: ")
            full_name = read_characters(client_socket)
            if register_user(username.strip(), password.strip(), email.strip(), full_name.strip()):
                client_socket.send(b"\r\nRegistration successful. You can now log in.\r\n")
                log_activity(f"New user registered: {username.strip()}")
            else:
                client_socket.send(b"\r\nRegistration failed. The username is already taken.\r\n")
        elif choice.strip() == '2':
            client_socket.send(b"\r\nLogin:\r\n")
            client_socket.send(b"\r\nEnter your username: ")
            username = read_characters(client_socket)
            client_socket.send(b"\r\nEnter your password: ")
            password = read_characters(client_socket)
            if authenticate_user(username.strip(), password.strip()):
                client_socket.send(b"\r\nLogin successful. Welcome, " + username.strip().encode('utf-8') + b"!\r\n")
                log_activity(f"{username.strip()} logged in.")
                return username.strip()
            else:
                client_socket.send(b"\r\nLogin failed. Invalid username or password.\r\n")
        elif choice.strip() == '3':
            client_socket.send(b"\r\nGoodbye!\r\n")
            client_socket.close()
            return None
        else:
            client_socket.send(b"\r\nInvalid choice. Please try again.\r\n")

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 12345))
    server.listen(5)
    print("Server is listening on port 12345...")

    while True:
        client_socket, addr = server.accept()
        print(f"Accepted connection from {addr[0]}:{addr[1]}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.start()

if __name__ == "__main__":
    main()
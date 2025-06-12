
from app.models.user import User


def get_password_hash(password: str) -> str:
    """Hashes a plaintext password."""
    return pwd_context.hash(password)

# --- New function to initialize database and admin user ---
def initialize_database_and_admin_user():
    print("Attempting to initialize database and admin user...")

    # Sleep briefly to ensure file system mounts are stable (optional, but can help)
    time.sleep(5) 

    # Construct the full path to your SQLite database file
    # Assuming your database file is named 'smartdoc.db' and lives in the DB_DIR
    db_file_name = "smartdoc.db" # Or whatever your actual database file name is
    db_full_path = os.path.join(DB_DIR, db_file_name)
    
    # Ensure the database directory exists (redundant if create_required_directories runs first, but safe)
    os.makedirs(DB_DIR, exist_ok=True)
    print(f"Ensured database directory '{DB_DIR}' exists.")

    db_file_exists = os.path.exists(db_full_path)

    if not db_file_exists:
        print(f"Database file '{db_full_path}' not found. Creating schema.")
        try:
            # Create all tables defined in your Base (from app.database)
            Base.metadata.create_all(bind=engine)
            print("Database tables created successfully.")
        except Exception as e:
            print(f"Error creating database tables: {e}")
            # It's critical for tables to exist, so you might want to raise here
            raise

    # Proceed to create/update admin user
    with SessionLocal() as db:
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_raw_password = os.getenv("ADMIN_PASSWORD")

        if not admin_email or not admin_raw_password:
            print("WARNING: ADMIN_EMAIL or ADMIN_PASSWORD environment variables not set. Skipping admin user initialization.")
            print("Please ensure these are set in your .env file or deployment environment.")
            return

        print(f"Checking for admin user with email: {admin_email}")
        existing_admin = db.query(User).filter(User.email == admin_email).first()

        if not existing_admin:
            print(f"Admin user '{admin_email}' not found. Creating new admin user.")
            hashed_password = get_password_hash(admin_raw_password)
            new_admin = User(
                username="Initial Admin", # You can make this configurable too
                email=admin_email,
                hashed_password=hashed_password,
                is_admin=True,
                is_active=True,
                is_created=datetime.utcnow()
                # Add any other required fields for your User model (e.g., created_at)
                # Example: created_at=datetime.utcnow() (requires datetime import)
            )
            db.add(new_admin)
            db.commit()
            db.refresh(new_admin)
            print(f"Admin user '{admin_email}' created successfully.")
        else:
            print(f"Admin user '{admin_email}' already exists. Ensuring admin privileges and password.")
            
            # Ensure the existing user is an admin
            if not existing_admin.is_admin:
                existing_admin.is_admin = True
                print(f"User '{admin_email}' granted admin privileges.")
            
            # Check if password needs to be updated (e.g., if it changed in .env)
            # This is optional and depends on whether you want to force password sync
            if not pwd_context.verify(admin_raw_password, existing_admin.hashed_password):
                 print(f"Updating password for admin user '{admin_email}'.")
                 existing_admin.hashed_password = get_password_hash(admin_raw_password)
            
            db.commit()
            db.refresh(existing_admin)
            print(f"Admin user '{admin_email}' state updated.")

    print("Database and admin initialization complete.")
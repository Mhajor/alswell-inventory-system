from sqlalchemy import create_engine, text

DATABASE_URL = "mysql+pymysql://root:root1234@localhost:3306/alswell_retail_inventory"
engine = create_engine(DATABASE_URL)

with engine.connect() as connection:
    try:
        print("Applying timestamp schema patch to 'orders' table...")
        # Alter the table structure to add the column safely
        connection.execute(text("ALTER TABLE orders ADD COLUMN order_date DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL;"))
        connection.commit()
        print("Success! 'order_date' column successfully added to MySQL.")
    except Exception as e:
        print(f"Notice: {e} (The column might already exist or the table is locked.)")
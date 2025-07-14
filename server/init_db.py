from db import engine
from models import Base

print("🛠️ Creating database tables...")
Base.metadata.create_all(bind=engine)
print("✅ Tables created successfully.")

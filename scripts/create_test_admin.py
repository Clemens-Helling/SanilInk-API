import asyncio
import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path so `import app...` works when running this script directly
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.tenants.models import Tenant
from app.users.models import User


async def main(email: str, username: str, customer_number: str, first_name: str | None, last_name: str | None, permission: str):
    async with async_session_factory() as session:
        # Ensure tenant exists
        result = await session.execute(select(Tenant).where(Tenant.customer_number == customer_number))
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(customer_number=customer_number)
            session.add(tenant)
            await session.flush()
            print(f"Created tenant id={tenant.customer_id} customer_number={customer_number}")
        else:
            print(f"Using existing tenant id={tenant.customer_id} customer_number={customer_number}")

        # Check if user exists by email
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.permission = permission
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.customer_id = tenant.customer_id
            user.is_active = True
            session.add(user)
            await session.flush()
            print(f"Updated user id={user.user_id} email={email} permission={permission}")
        else:
            user = User(
                customer_id=tenant.customer_id,
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                permission=permission,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            print(f"Created user id={user.user_id} email={email} permission={permission}")

        await session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update a test admin user in the database.")
    parser.add_argument("--email", default="test.admin@example.com")
    parser.add_argument("--username", default="testadmin")
    parser.add_argument("--customer-number", dest="customer_number", default="test-customer")
    parser.add_argument("--first-name", dest="first_name", default="Test")
    parser.add_argument("--last-name", dest="last_name", default="Admin")
    parser.add_argument("--permission", default="admin", help="Permission string to set on the user (default: admin)")

    args = parser.parse_args()

    # Ensure settings are loaded from env/.env. The script will use settings.database_url.
    if not settings.database_url:
        raise SystemExit("settings.database_url is not set. Set DATABASE_URL in env or .env before running.")

    asyncio.run(
        main(
            email=args.email,
            username=args.username,
            customer_number=args.customer_number,
            first_name=args.first_name,
            last_name=args.last_name,
            permission=args.permission,
        )
    )

import asyncio
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete
from sqlmodel import select

from app.course.models import Course
from app.db.session import get_session
from app.llm.models import Prompt

import argparse


async def clear_model_data(model: str, dry_run=False):
    async with get_session() as db:
        query = await db.exec(select(Prompt).where(Prompt.model == model))
        prompts = query.all()
        print(f"Found {len(prompts)} prompts for model {model}.")
        if not dry_run:
            await db.exec(delete(Prompt).where(Prompt.model == model))

        query = await db.exec(select(Course).where(Course.model == model))
        courses = query.all()
        print(f"Found {len(courses)} courses for model {model}.")
        if not dry_run:
            await db.exec(delete(Course).where(Course.model == model))
            await db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove all data related to a specific model.")
    parser.add_argument("model", help="model name")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually delete anything.")
    args = parser.parse_args()

    asyncio.run(clear_model_data(args.model, args.dry_run))




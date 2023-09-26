from invoke import task
from app.settings import settings

DEV_ENV = {
    "DATABASE_URL": settings.DATABASE_URL,
    "PYTHONPATH": "."
}

@task
def generate_migrations(ctx):
    ctx.run("alembic revision --autogenerate", env=DEV_ENV)


@task
def migrate_dev(ctx):
    ctx.run("alembic upgrade head", env=DEV_ENV)

@task
def downgrade_dev(ctx):
    ctx.run("alembic downgrade -1", env=DEV_ENV)


@task
def clear_dev_db(ctx):
    ctx.run('psql postgres -c "drop database textbook;"')


@task
def create_dev_db(ctx):
    ctx.run('psql postgres -c "create database textbook;"')


@task
def reset_dev_db(ctx):
    clear_dev_db(ctx)
    create_dev_db(ctx)
    migrate_dev(ctx)


@task
def reset_migrations(ctx):
    ctx.run("rm -rf alembic/versions/*")
    generate_migrations(ctx)
    migrate_dev(ctx)


@task
def lint(ctx):
    ctx.run("pylint --load-plugins pylint_pydantic app")


@task
def black(ctx):
    ctx.run(
        "autoflake --imports=sqlmodel,sqlalchemy,typing --recursive --in-place app --exclude=__init__.py,tables.py,main.py,db.py,alembic,data,cache")
    ctx.run("isort app --profile black")
    ctx.run("black app --exclude tables.py,main.py,db.py,__init__.py,alembic,data,cache")
